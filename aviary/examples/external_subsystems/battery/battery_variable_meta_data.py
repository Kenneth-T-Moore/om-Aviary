import numpy as np
import aviary.api as av
from aviary.examples.external_subsystems.battery.battery_variables import (
    Aircraft,
    Dynamic,
)


ExtendedMetaData = av.CoreMetaData


##### BATTERY VALUES #####

av.add_meta_data(
    Aircraft.Battery.CURRENT_MAX,
    units="A",
    desc="Max current through the pack",
    default_value=10.,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.ENERGY_REQUIRED,
    units="kW*h",
    desc="Required battery energy",
    default_value=65.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.HEAT_CAPACITY,
    units="J/(kg*K)",
    desc="mass-averaged specific heat (cp)",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.N_PARALLEL,
    units=None,
    desc="Number of cells in parallel, based on power constraint",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.N_SERIES,
    units=None,
    desc="Number of cells in series",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.VOLTAGE,
    units="V",
    desc="Nominal bus voltage",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

##### CASE VALUES #####

av.add_meta_data(
    Aircraft.Battery.Case.HEAT_CAPACITY,
    units="J/(kg*K)",
    desc="Mass-averaged specific heat (cp)",
    default_value=921.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.Case.WEIGHT_FRAC,
    units=None,
    desc="Case weight per unit of cell weight",
    default_value=1.3,
    meta_data=ExtendedMetaData
)

##### CELL VALUES #####

av.add_meta_data(
    Aircraft.Battery.Cell.DISCHARGE_RATE,
    units="A",
    desc="Cell discharge rate",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.Cell.ENERGY_CAPACITY_MAX,
    units="A*h",
    desc="Maximum energy capacity of a single cell (Q_max)",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.Cell.HEAT_CAPACITY,
    units="J/(kg*K)",
    desc="Specific heat of a battery cell",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.Cell.MASS,
    units="kg",
    desc="Mass of a single cell",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.Cell.VOLTAGE_LOW,
    units="V",
    desc="Cell Voltage at low SOC, before drop-off",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Battery.Cell.VOLUME,
    units="inch**3",
    desc="Volume of a single cell",
    default_value=1.0,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Dynamic.Battery.CURRENT,
    units="A",
    desc="Current output from the battery",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.EFFICIENCY,
    units="unitless",
    desc="Current efficiency of the battery",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.HEAT_OUT,
    units="W",
    desc="Heat generated by the battery",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.STATE_OF_CHARGE,
    units=None,
    desc="State of charge of the battery (SOC)",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.STATE_OF_CHARGE_RATE,
    units="1/s",
    desc="Time rate of change of the battery state of charge",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.TEMPERATURE,
    units="K",
    desc="Battery pack bulk temperature",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.VOLTAGE,
    units="V",
    desc="Total battery voltage",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.VOLTAGE_THEVENIN,
    units="V",
    desc="Thevenin (Polarization) voltage",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)

av.add_meta_data(
    Dynamic.Battery.VOLTAGE_THEVENIN_RATE,
    units="V/s",
    desc="Time rate of change of Thevenin voltage",
    default_value=0.0,
    multivalue=True,
    meta_data=ExtendedMetaData,
)
