import numpy as np
from enum import Enum
import warnings
import openmdao.api as om
from openmdao.utils.units import convert_units

from aviary.subsystems.propulsion.utils import PropModelVariables, default_prop_units
from aviary.variable_info.options import get_option_defaults
from aviary.variable_info.variables import Aircraft, Dynamic, Settings
from aviary.utils.aviary_values import AviaryValues, NamedValues, get_keys, get_items
from aviary.utils.csv_data_file import read_data_file
from aviary.utils.functions import get_path


MACH = PropModelVariables.MACH
CP = PropModelVariables.CP
CT = PropModelVariables.CT
J = PropModelVariables.J

aliases = {
    # whitespaces are replaced with underscores converted to lowercase before
    # comparison with keys
    MACH: ['m', 'mn', 'mach', 'mach_number'],
    CP: ['cp', 'power_coefficient'],
    CT: ['ct', 'thrust_coefficient'],
    J: ['j', 'advance_ratio'],
}

class PropellerMap(om.ExplicitComponent):
    """
    Attributes
    ----------
    name : str ('propeller')
        Object label.
    options : AviaryValues (<empty>)
        Inputs and options related to propeller model.
    data : NamedVaues (<empty>), optional
        propeller map data.
    mach_type: str ('mach' or 'helical_mach')
    """

    def __init__(self, name='propeller', options = None,
                 data: NamedValues = None, mach_type = 'mach'):
        super().__init__()

        # copy of raw data read from data_file or memory, never modified or used outside
        #     PropellerMap
        self._original_data = {key: np.array([]) for key in PropModelVariables}
        # working copy of propeller performance data, is modified during data pre-processing
        self.data = {key: np.array([]) for key in PropModelVariables}

        # Create dict for variables present in propeller data with associated units
        self.propeller_variables = {}

        data_file = options.get_val(Aircraft.Engine.PROPELLER_DATA_FILE)
        self._read_data(data_file)

    def _read_data(self, data_file):
        # read csv file
        raw_data = read_data_file(data_file, aliases=aliases)

        message = f'<{data_file}>'
        # Loop through all variables in provided data. Track which valid variables are
        #    included with the data and save raw data for reference
        for key in get_keys(raw_data):
            val, units = raw_data.get_item(key)
            if key in aliases:
                # Convert data to expected units. Required so settings like tolerances
                # that assume units work as expected
                try:
                    val = np.array([convert_units(i, units, default_prop_units[key])
                                   for i in val])
                except TypeError:
                    raise TypeError(f"{message}: units of '{units}' provided for "
                                    f'<{key.name}> are not compatible with expected units '
                                    f'of {default_prop_units[key]}')

                # propeller_variables currently only used to store "valid" engine variables
                # as defined in EngineModelVariables Enum
                self.propeller_variables[key] = default_prop_units[key]

            else:
                if self.get_val(Settings.VERBOSITY).value >= 1:
                    warnings.warn(
                        f'{message}: header <{key}> was not recognized, and will be skipped')

            # save all data in self._original_data, including skipped variables
            self._original_data[key] = val

        if not self.propeller_variables:
            raise UserWarning(f'No valid propeller variables found in data for {message}')

        # set flags using updated propeller_variables
        #self._set_variable_flags()

        # Copy data from original data (never modified) to working data (changed through
        #    sorting, generating missing data, etc.)
        # self.data contains all keys in PropellerModelVariables
        for key in self.data:
            self.data[key] = self._original_data[key]

    def read_and_set_mach_type(self, data_file):
        # sample header:
        # created 06/24/24 at 17:13
        # GASP propeller map converted from PropFan.map
        # Propfan format - CT = f(Mach, Adv Ratio & CP)
        # mach_type = mach
        # Hamilton Standard 10 Bladed Propfan Performance Deck:  Ct Tables

        fp = get_path(data_file)
        with open(fp, "r") as f:
            line = f.readline()
            line = f.readline()
            line = f.readline()
            line = f.readline()  # read 4th line
            mach_type = line.split()[3]  # get token 3
        return mach_type
       
    def initialize(self):
        self.options.declare(
            'aviary_options', types=AviaryValues,
            desc='collection of Aircraft/Mission specific options')
        self.options.declare('num_nodes', default=1, types=int)

    def build_propeller_interpolator(self, num_nodes, options = None):
        """
        Builds the OpenMDAO metamodel component for the propeller map.
        """
        interp_method = options.get_val(Aircraft.Engine.INTERPOLATION_METHOD)
        # interpolator object for propeller data
        propeller = om.MetaModelSemiStructuredComp(
            method=interp_method, extrapolate=True, vec_size=num_nodes)

        # add inputs and outputs to interpolator
        # depending on p, selected_mach can be Mach number (Dynamic.Mission.MACH) or helical Mach number
        propeller.add_input('selected_mach',
                         self.data[MACH],
                         units='unitless',
                         desc='Current flight Mach number')
        propeller.add_input("power_coefficient",
                         self.data[CP],
                         units='unitless',
                         desc='Current power coefficient')
        propeller.add_input("advance_ratio",
                         self.data[J],
                         units='unitless',
                         desc='Current advance ratio')
        propeller.add_output('thrust_coefficient',
                          self.data[CT],
                          units='unitless',
                          desc='Current thrust coefficient')
        
        return propeller
