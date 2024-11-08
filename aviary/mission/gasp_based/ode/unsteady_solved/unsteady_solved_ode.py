import numpy as np
import openmdao.api as om
from aviary.subsystems.atmosphere.atmosphere import Atmosphere

from aviary.constants import RHO_SEA_LEVEL_ENGLISH as rho_sl
from aviary.mission.gasp_based.ode.base_ode import BaseODE
from aviary.mission.gasp_based.ode.params import ParamPort
from aviary.mission.gasp_based.ode.unsteady_solved.gamma_comp import GammaComp
from aviary.mission.gasp_based.ode.unsteady_solved.unsteady_solved_flight_conditions import \
    UnsteadySolvedFlightConditions
from aviary.mission.gasp_based.ode.unsteady_solved.unsteady_solved_eom import UnsteadySolvedEOM
from aviary.variable_info.enums import SpeedType, LegacyCode
from aviary.variable_info.variables import Dynamic
from aviary.subsystems.aerodynamics.aerodynamics_builder import AerodynamicsBuilderBase
from aviary.subsystems.propulsion.propulsion_builder import PropulsionBuilderBase
from aviary.variable_info.variable_meta_data import _MetaData


class UnsteadySolvedODE(BaseODE):
    """
    This 2D aircraft ODE provides the rate of change of time per unit range covered.

    Altitude and velocity at various points along the trajectory are provided, along with
    their corresponding rates of change. The latter are automatically generated by
    differentiating the interpolating polynomials fit to the values. Range is the
    integration variable for this ODE.

    For the given altitude/velocity trajectory, this ODE then provides the alpha and
    thrust history that make that given trajectory physically realizable.

    Thrust is allowed to take on physically-nonsensical values (negative, or extremely
    large magnitudes) to provide robust convergence of the nonlinear solver. This
    discrepancy is then resolved by imposing a path constraint that the thrust needed to
    perform the trajectory equals the thrust generated by the propulsion system with its
    given settings.
    """

    def initialize(self):
        super().initialize()
        self.options.declare(
            "ground_roll",
            types=bool,
            default=False,
            desc="True if the aircraft is confined to the ground. Removes altitude rate "
            "as an output and adjusts the TAS rate equation.",
        )
        self.options.declare(
            "clean",
            types=bool,
            default=False,
            desc="If true then no flaps or gear are included. Useful for high-speed "
            "flight phases.",
        )
        self.options.declare(
            "include_param_comp",
            types=bool,
            default=True,
            desc="If true then add a ParamComp to this ODE. Useful for smaller usages "
            "of this ODE not within a full trajectory or a pre-mission group.",
        )
        self.options.declare(
            "input_speed_type",
            default=SpeedType.TAS,
            types=SpeedType,
            desc="Airspeed type specified as input.")
        self.options.declare(
            'throttle_enforcement',
            default='path_constraint',
            values=['path_constraint', 'boundary_constraint', 'bounded', None],
            desc='flag to enforce throttle constraints on the path or at the segment '
            'boundaries or using solver bounds',
        )
        self.options.declare(
            'initial_throttle_lapse', default=0.0,
            types=float,
            desc='initial fraction of total throttle change across phase for linear throttle control'
        )
        self.options.declare(
            'final_throttle_lapse', default=0.0,
            types=float,
            desc='final fraction of total throttle change across phase for linear throttle control'
        )
        #self.options.declare(
        #    'isa_deltaT', default=0.0,
        #    types=float,
        #    desc='Temperature delta (deg R) from typical International Standard Atmosphere (ISA) conditions',
        #)
        self.options.declare(
            'external_subsystems', default=[],
            desc='list of external subsystem builder instances to be added to the ODE')
        self.options.declare(
            'meta_data', default=_MetaData,
            desc='metadata associated with the variables to be passed into the ODE')

    def setup(self):
        nn = self.options["num_nodes"]
        ground_roll = self.options["ground_roll"]
        input_speed_type = self.options["input_speed_type"]
        aviary_options = self.options['aviary_options']
        subsystem_options = self.options['subsystem_options']
        core_subsystems = self.options['core_subsystems']
        throttle_enforcement = self.options['throttle_enforcement']
        initial_throttle_lapse = self.options['initial_throttle_lapse']
        final_throttle_lapse = self.options['final_throttle_lapse']
        #isa_deltaT = self.options['isa_deltaT']

        if self.options["include_param_comp"]:
            # TODO: paramport
            self.add_subsystem("params", ParamPort(), promotes=["*"])

        self.add_subsystem(
            name='atmosphere',
            subsys=Atmosphere(num_nodes=nn, output_dsos_dh=True),#, isa_deltaT=isa_deltaT),
            promotes_inputs=[Dynamic.Mission.ALTITUDE],
            promotes_outputs=[
                Dynamic.Mission.DENSITY,
                Dynamic.Mission.SPEED_OF_SOUND,
                Dynamic.Mission.TEMPERATURE,
                Dynamic.Mission.STATIC_PRESSURE,
                "viscosity_corr",
                "drhos_dh_corr",
                "dsos_dh_corr",
            ],
        )

        self.add_subsystem("flight_path_angle",
                           GammaComp(num_nodes=nn),
                           promotes_inputs=["*"],
                           promotes_outputs=["*"])

        self.add_subsystem(
            "fc",
            UnsteadySolvedFlightConditions(
                num_nodes=nn, ground_roll=ground_roll, input_speed_type=input_speed_type
            ),
            promotes_inputs=['*'],
            promotes_outputs=['*'],
        )

        control_iter_group = self.add_subsystem("control_iter_group",
                                                subsys=om.Group(),
                                                promotes_inputs=["*"],
                                                promotes_outputs=["*"])

        # Also need to change the run script and the iter group solver when using this;
        # just testing for now
        throttle_balance_group = self.add_subsystem("throttle_balance_group",
                                                    om.Group(),
                                                    promotes=["*"])

        throttle_balance_comp = om.BalanceComp()
        throttle_balance_comp.add_balance(
            Dynamic.Mission.THROTTLE,
            units="unitless",
            val=np.ones(nn) * 0.5,
            lhs_name=Dynamic.Mission.THRUST_TOTAL,
            rhs_name="thrust_req",
            eq_units="lbf",
            normalize=False,
            lower=0.0 if throttle_enforcement == 'bounded' else None,
            upper=1.0 if throttle_enforcement == 'bounded' else None,
            res_ref=1.0e6,
        )

        throttle_balance_group.add_subsystem("throttle_balance_comp", subsys=throttle_balance_comp,
                                             promotes_inputs=["*"],
                                             promotes_outputs=["*"])

        throttle_balance_group.nonlinear_solver = om.NewtonSolver(solve_subsystems=True,
                                                                  atol=1.0e-10,
                                                                  rtol=1.0e-10,
                                                                  )
        throttle_balance_group.nonlinear_solver.linesearch = om.BoundsEnforceLS()
        throttle_balance_group.linear_solver = om.DirectSolver(assemble_jac=True)
        throttle_balance_group.nonlinear_solver.options['err_on_non_converge'] = True

        # add an ExecComp that calculates the time duration of the phase
        phase_time_comp = om.ExecComp('phase_time = time - time[0]', units='s', 
                           time={'shape': nn},
                           phase_time={'shape': nn})
        self.add_subsystem('compute_phase_time', phase_time_comp,
                           promotes_inputs=['time'],
                           promotes_outputs=['phase_time'])

        # add ExecComp to compute residual between throttle and prescribed throttle lapse profile
        throttle_residual_comp = om.ExecComp('throttle_residual = computed_throttle - prescribed_throttle',
                           prescribed_throttle={'val':np.linspace(initial_throttle_lapse, final_throttle_lapse, nn, endpoint=True)},
                           throttle_residual={'shape': nn},
                           computed_throttle={'shape': nn})
        self.add_subsystem('compute_throttle_residual', throttle_residual_comp,
                           promotes_inputs=[('computed_throttle', Dynamic.Mission.THROTTLE)],
                           promotes_outputs=['throttle_residual'])

        kwargs = {
            'num_nodes': nn,
            'aviary_inputs': aviary_options,
            'method': 'low_speed',
        }
        if self.options['clean']:
            kwargs['method'] = 'cruise'
        for subsystem in core_subsystems:
            # check if subsystem_options has entry for a subsystem of this name
            if subsystem.name in subsystem_options:
                kwargs.update(subsystem_options[subsystem.name])
            system = subsystem.build_mission(**kwargs)
            if system is not None:
                if isinstance(subsystem, AerodynamicsBuilderBase):
                    mission_inputs = subsystem.mission_inputs(**kwargs)
                    if subsystem.code_origin is LegacyCode.FLOPS and 'angle_of_attack' in mission_inputs:
                        mission_inputs.remove('angle_of_attack')
                        mission_inputs.append(('angle_of_attack', 'alpha'))
                    control_iter_group.add_subsystem(subsystem.name,
                                                     system,
                                                     promotes_inputs=mission_inputs,
                                                     promotes_outputs=subsystem.mission_outputs(**kwargs))
                elif isinstance(subsystem, PropulsionBuilderBase):
                    throttle_balance_group.add_subsystem(subsystem.name,
                                                         system,
                                                         promotes_inputs=subsystem.mission_inputs(
                                                             **kwargs),
                                                         promotes_outputs=subsystem.mission_outputs(**kwargs))
                else:
                    self.add_subsystem(subsystem.name,
                                       system,
                                       promotes_inputs=subsystem.mission_inputs(
                                           **kwargs),
                                       promotes_outputs=subsystem.mission_outputs(**kwargs))

        eom_comp = UnsteadySolvedEOM(num_nodes=nn, ground_roll=ground_roll)

        input_list = [
            '*',
            (Dynamic.Mission.THRUST_TOTAL, "thrust_req"),
            Dynamic.Mission.VELOCITY,
        ]
        control_iter_group.add_subsystem("eom", subsys=eom_comp,
                                         promotes_inputs=input_list,
                                         promotes_outputs=["*"])

        thrust_alpha_bal = om.BalanceComp()
        if not self.options['ground_roll']:
            thrust_alpha_bal.add_balance("alpha",
                                         units="rad",
                                         val=np.zeros(nn),
                                         lhs_name="dgam_dt_approx",
                                         rhs_name="dgam_dt",
                                         eq_units="rad/s",
                                         #lower=-np.pi/12,
                                         #upper=np.pi/12,
                                         normalize=False)

        thrust_alpha_bal.add_balance("thrust_req",
                                     units="N",
                                     val=100*np.ones(nn),
                                     lhs_name="dTAS_dt_approx",
                                     rhs_name="dTAS_dt",
                                     eq_units="m/s**2",
                                     normalize=False)

        control_iter_group.add_subsystem("thrust_alpha_bal", subsys=thrust_alpha_bal,
                                         promotes_inputs=["*"],
                                         promotes_outputs=["*"])

        control_iter_group.nonlinear_solver = om.NewtonSolver(solve_subsystems=True,
                                                              atol=1.0e-10,
                                                              rtol=1.0e-10)
        # control_iter_group.nonlinear_solver.linesearch = om.BoundsEnforceLS()
        control_iter_group.linear_solver = om.DirectSolver(assemble_jac=True)

        self.add_subsystem("mass_rate",
                           om.ExecComp("dmass_dr = fuelflow * dt_dr",
                                       fuelflow={"units": "lbm/s", "shape": nn},
                                       dt_dr={"units": "s/distance_units", "shape": nn},
                                       dmass_dr={"units": "lbm/distance_units",
                                                 "shape": nn,
                                                 "tags": ['dymos.state_rate_source:mass',
                                                          'dymos.state_units:lbm']},
                                       has_diag_partials=True),
                           promotes_inputs=[
                               ("fuelflow", Dynamic.Mission.FUEL_FLOW_RATE_NEGATIVE_TOTAL), "dt_dr"],
                           promotes_outputs=["dmass_dr"])
        
        self.add_subsystem(
            'char_impedance_comp',
            om.ExecComp(
                'char_impedance = density * speed_of_sound',
                char_impedance={'units': 'kg/(m**2*s)', 'shape': nn},
                density={'units': 'kg/m**3', 'shape': nn},
                speed_of_sound={'units': 'm/s', 'shape': nn}),
            promotes_inputs=[('density', Dynamic.Mission.DENSITY), # WAS 'rho'
                             ('speed_of_sound', Dynamic.Mission.SPEED_OF_SOUND)],
            promotes_outputs=['char_impedance'])

        if self.options["include_param_comp"]:
            ParamPort.set_default_vals(self)

        onn = np.ones(nn)
        self.set_input_defaults(name=Dynamic.Mission.DENSITY,
                                val=rho_sl * onn, units="slug/ft**3")
        self.set_input_defaults(
            name=Dynamic.Mission.SPEED_OF_SOUND,
            val=1116.4 * onn,
            units="ft/s")
        if not self.options['ground_roll']:
            self.set_input_defaults(
                name=Dynamic.Mission.FLIGHT_PATH_ANGLE, val=0.0 * onn, units="rad")
        self.set_input_defaults(name=Dynamic.Mission.VELOCITY,
                                val=250. * onn, units="kn")
        self.set_input_defaults(
            name=Dynamic.Mission.ALTITUDE,
            val=10000. * onn,
            units="ft")
        self.set_input_defaults(name="dh_dr", val=0. * onn, units="ft/distance_units")
        self.set_input_defaults(name="d2h_dr2", val=0. * onn,
                                units="ft/distance_units**2")
