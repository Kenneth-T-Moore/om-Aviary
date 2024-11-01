import numpy as np
import openmdao.api as om

from aviary.mission.gasp_based.ode.base_ode import BaseODE
from aviary.mission.gasp_based.ode.groundroll_eom import GroundrollEOM
from aviary.mission.gasp_based.ode.params import ParamPort
from aviary.variable_info.variables import Aircraft, Dynamic
from aviary.variable_info.enums import AnalysisScheme
from aviary.subsystems.aerodynamics.aerodynamics_builder import AerodynamicsBuilderBase
from aviary.variable_info.variable_meta_data import _MetaData
from aviary.mission.gasp_based.ode.time_integration_base_classes import add_SGM_required_inputs


class GroundrollODE(BaseODE):
    """ODE for takeoff ground roll.

    This phase begins at the point when the aircraft begins accelerating down the runway
    to takeoff, and runs until the aircraft begins to rotate its front tire off the
    runway.
    """

    def initialize(self):
        super().initialize()
        self.options.declare(
            'external_subsystems', default=[],
            desc='list of external subsystem builder instances to be added to the ODE')
        self.options.declare(
            'meta_data', default=_MetaData,
            desc='metadata associated with the variables to be passed into the ODE')
        self.options.declare(
            'set_input_defaults', default=True,
            desc='set input defaults for the ODE')

    def setup(self):
        nn = self.options["num_nodes"]
        analysis_scheme = self.options["analysis_scheme"]
        aviary_options = self.options['aviary_options']
        core_subsystems = self.options['core_subsystems']
        subsystem_options = self.options['subsystem_options']

        if analysis_scheme is AnalysisScheme.SHOOTING:
            add_SGM_required_inputs(self, {
                Dynamic.Mission.DISTANCE: {'units': 'ft'},
            })

        # TODO: paramport
        self.add_subsystem("params", ParamPort(), promotes=["*"])

        self.add_atmosphere(nn)

        # broadcast scalar i_wing to alpha for aero
        #wing_incidence = aviary_options.get_val(Aircraft.Wing.INCIDENCE, units='deg')
        self.add_subsystem("init_alpha",
                           om.ExecComp("alpha = i_wing",
                                       i_wing={"units": "deg", "val": 1.1},
                                       alpha={"units": "deg", "val": 1.1*np.ones(nn)},),
                           promotes=[("i_wing", Aircraft.Wing.INCIDENCE),
                                     "alpha"])

        kwargs = {'num_nodes': nn, 'aviary_inputs': aviary_options,
                  'method': 'low_speed'}
        for subsystem in core_subsystems:
            # check if subsystem_options has entry for a subsystem of this name
            if subsystem.name in subsystem_options:
                kwargs.update(subsystem_options[subsystem.name])
            system = subsystem.build_mission(**kwargs)
            if system is not None:
                self.add_subsystem(subsystem.name,
                                   system,
                                   promotes_inputs=subsystem.mission_inputs(**kwargs),
                                   promotes_outputs=subsystem.mission_outputs(**kwargs))
            if type(subsystem) is AerodynamicsBuilderBase:
                self.promotes(
                    subsystem.name,
                    inputs=["alpha"],
                    src_indices=np.zeros(nn, dtype=int),
                )

        self.add_subsystem("groundroll_eom", GroundrollEOM(num_nodes=nn), promotes=["*"])

        self.add_subsystem("exec", om.ExecComp(f"over_a = velocity / velocity_rate",
                                               velocity_rate={"units": "kn/s",
                                                              "val": np.ones(nn)},
                                               velocity={"units": "kn",
                                                         "val": np.ones(nn)},
                                               over_a={"units": "s", "val": np.ones(nn)},
                                               has_diag_partials=True,
                                               ),
                           promotes=["*"])

        self.add_subsystem("exec2", om.ExecComp(f"dt_dv = 1 / velocity_rate",
                                                velocity_rate={"units": "kn/s",
                                                               "val": np.ones(nn)},
                                                dt_dv={"units": "s/kn",
                                                       "val": np.ones(nn)},
                                                has_diag_partials=True,
                                                ),
                           promotes=["*"])

        self.add_subsystem(
            "exec3",
            om.ExecComp(
                "dmass_dv = mass_rate * dt_dv",
                mass_rate={
                    "units": "lbm/s",
                    "val": np.ones(nn)},
                dt_dv={
                    "units": "s/kn",
                    "val": np.ones(nn)},
                dmass_dv={
                    "units": "lbm/kn",
                    "val": np.ones(nn)},
                has_diag_partials=True,
            ),
            promotes_outputs=[
                "dmass_dv",
            ],
            promotes_inputs=[
                ("mass_rate",
                 Dynamic.Mission.FUEL_FLOW_RATE_NEGATIVE_TOTAL),
                "dt_dv"])

        ParamPort.set_default_vals(self)

        if self.options['set_input_defaults']:
            self.set_input_defaults("t_init_flaps", val=100.)
            self.set_input_defaults("t_init_gear", val=100.)
            self.set_input_defaults('aero_ramps.flap_factor:final_val', val=1.)
            self.set_input_defaults('aero_ramps.gear_factor:final_val', val=1.)
            self.set_input_defaults('aero_ramps.flap_factor:initial_val', val=1.)
            self.set_input_defaults('aero_ramps.gear_factor:initial_val', val=1.)
            self.set_input_defaults("t_curr", val=np.zeros(nn), units="s")

        self.set_input_defaults(Dynamic.Mission.FLIGHT_PATH_ANGLE,
                                val=np.zeros(nn), units="deg")
        self.set_input_defaults(Dynamic.Mission.ALTITUDE, val=np.zeros(nn), units="ft")
        self.set_input_defaults(Dynamic.Mission.VELOCITY, val=np.zeros(nn), units="kn")
        self.set_input_defaults(Dynamic.Mission.VELOCITY_RATE,
                                val=np.zeros(nn), units="kn/s")

        self.set_input_defaults(Aircraft.Wing.INCIDENCE, val=-0.854237, units="deg") # was 1
