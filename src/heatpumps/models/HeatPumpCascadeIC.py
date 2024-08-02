import os
from datetime import datetime
from time import time

import numpy as np
import pandas as pd
from CoolProp.CoolProp import PropsSI as PSI
from tespy.components import (Compressor, Condenser, CycleCloser,
                              HeatExchanger, Pump, SimpleHeatExchanger, Sink,
                              Source, Valve)
from tespy.connections import Bus, Connection, Ref
from tespy.networks import Network
from tespy.tools.characteristics import CharLine
from tespy.tools.characteristics import load_default_char as ldc

if __name__ == '__main__':
    from HeatPumpBase import HeatPumpBase
else:
    from .HeatPumpBase import HeatPumpBase


class HeatPumpCascadeIC(HeatPumpBase):
    """Two stage cascading heat pump with two refrigerants and intercooler."""

    def __init__(self, params):
        """Initialize model and set necessary attributes."""
        self.params = params

        self.wf1 = self.params['fluids']['wf1']
        self.wf2 = self.params['fluids']['wf2']
        self.si = self.params['fluids']['si']
        self.so = self.params['fluids']['so']

        self.comps = dict()
        self.conns = dict()
        self.buses = dict()

        self.nw = Network(
            T_unit='C', p_unit='bar', h_unit='kJ / kg', m_unit='kg / s'
        )

        self.cop = np.nan
        self.epsilon = np.nan

        self.solved_design = False
        self.subdirname = (
                f"{self.params['setup']['type']}_"
                + f"{self.params['setup']['refrig1']}_"
                + f"{self.params['setup']['refrig2']}"
        )
        self.design_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 'stable', f'{self.subdirname}_design'
        ))
        self.validate_dir()

    def generate_components(self):
        """Initialize components of heat pump."""
        # Heat source
        self.comps['hs_ff'] = Source('Heat Source Feed Flow')
        self.comps['hs_bf'] = Sink('Heat Source Back Flow')
        self.comps['hs_pump'] = Pump('Heat Source Recirculation Pump')

        # Heat sink
        self.comps['cons_cc'] = CycleCloser('Consumer Cycle Closer')
        self.comps['cons_pump'] = Pump('Consumer Recirculation Pump')
        self.comps['cons'] = SimpleHeatExchanger('Consumer')

        # Upper cycle
        self.comps['cond'] = Condenser('Condenser')
        self.comps['cc2'] = CycleCloser('Main Cycle Closer 2')
        self.comps['valve2'] = Valve('Valve 2')
        self.comps['inter'] = Condenser('Intermediate Heat Exchanger')
        self.comps['lp_comp2'] = Compressor('Low Pressure Compressor 2')
        self.comps['ic2'] = SimpleHeatExchanger('Intercooler 2')
        self.comps['hp_comp2'] = Compressor('High Pressure Compressor 2')

        # Lower cycle
        self.comps['cc1'] = CycleCloser('Main Cycle Closer 1')
        self.comps['valve1'] = Valve('Valve 1')
        self.comps['evap'] = HeatExchanger('Evaporator')
        self.comps['lp_comp1'] = Compressor('Low Pressure Compressor 1')
        self.comps['ic1'] = SimpleHeatExchanger('Intercooler 1')
        self.comps['hp_comp1'] = Compressor('High Pressure Compressor 1')

    def generate_connections(self):
        """Initialize and add connections and buses to network."""
        # Upper Cycle Connections
        self.conns['A0'] = Connection(
            self.comps['cond'], 'out1', self.comps['cc2'], 'in1', 'A0'
        )
        self.conns['A1'] = Connection(
            self.comps['cc2'], 'out1', self.comps['valve2'], 'in1', 'A1'
        )
        self.conns['A2'] = Connection(
            self.comps['valve2'], 'out1', self.comps['inter'], 'in2', 'A2'
        )
        self.conns['A3'] = Connection(
            self.comps['inter'], 'out2', self.comps['lp_comp2'], 'in1', 'A3'
        )
        self.conns['A4'] = Connection(
            self.comps['lp_comp2'], 'out1', self.comps['ic2'], 'in1', 'A4'
        )
        self.conns['A5'] = Connection(
            self.comps['ic2'], 'out1', self.comps['hp_comp2'], 'in1', 'A5'
        )
        self.conns['A6'] = Connection(
            self.comps['hp_comp2'], 'out1', self.comps['cond'], 'in1', 'A6'
        )

        # Lower cycle connections
        self.conns['D0'] = Connection(
            self.comps['inter'], 'out1', self.comps['cc1'], 'in1', 'D0'
        )
        self.conns['D1'] = Connection(
            self.comps['cc1'], 'out1', self.comps['valve1'], 'in1', 'D1'
        )
        self.conns['D2'] = Connection(
            self.comps['valve1'], 'out1', self.comps['evap'], 'in2', 'D2'
        )
        self.conns['D3'] = Connection(
            self.comps['evap'], 'out2', self.comps['lp_comp1'], 'in1', 'D3'
        )
        self.conns['D4'] = Connection(
            self.comps['lp_comp1'], 'out1', self.comps['ic1'], 'in1', 'D4'
        )
        self.conns['D5'] = Connection(
            self.comps['ic1'], 'out1', self.comps['hp_comp1'], 'in1', 'D5'
        )
        self.conns['D6'] = Connection(
            self.comps['hp_comp1'], 'out1', self.comps['inter'], 'in1', 'D6'
        )

        self.conns['B1'] = Connection(
            self.comps['hs_ff'], 'out1', self.comps['evap'], 'in1', 'B1'
        )
        self.conns['B2'] = Connection(
            self.comps['evap'], 'out1', self.comps['hs_pump'], 'in1', 'B2'
        )
        self.conns['B3'] = Connection(
            self.comps['hs_pump'], 'out1', self.comps['hs_bf'], 'in1', 'B3'
        )

        self.conns['C0'] = Connection(
            self.comps['cons'], 'out1', self.comps['cons_cc'], 'in1', 'C0'
        )
        self.conns['C1'] = Connection(
            self.comps['cons_cc'], 'out1', self.comps['cons_pump'], 'in1', 'C1'
        )
        self.conns['C2'] = Connection(
            self.comps['cons_pump'], 'out1', self.comps['cond'], 'in2', 'C2'
        )
        self.conns['C3'] = Connection(
            self.comps['cond'], 'out2', self.comps['cons'], 'in1', 'C3'
        )

        self.nw.add_conns(*[conn for conn in self.conns.values()])

        # Buses
        mot_x = np.array([
            0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55,
            0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1, 1.05, 1.1, 1.15,
            1.2, 10
        ])
        mot_y = (np.array([
            0.01, 0.3148, 0.5346, 0.6843, 0.7835, 0.8477, 0.8885, 0.9145,
            0.9318, 0.9443, 0.9546, 0.9638, 0.9724, 0.9806, 0.9878, 0.9938,
            0.9982, 1.0009, 1.002, 1.0015, 1, 0.9977, 0.9947, 0.9909, 0.9853,
            0.9644
        ]) * 0.98)
        mot = CharLine(x=mot_x, y=mot_y)
        self.buses['power input'] = Bus('power input')
        self.buses['power input'].add_comps(
            {'comp': self.comps['lp_comp1'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['lp_comp2'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['hp_comp1'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['hp_comp2'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['hs_pump'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['cons_pump'], 'char': mot, 'base': 'bus'}
        )

        self.buses['heat input'] = Bus('heat input')
        self.buses['heat input'].add_comps(
            {'comp': self.comps['hs_ff'], 'base': 'bus'},
            {'comp': self.comps['hs_bf'], 'base': 'component'}
        )

        self.buses['heat output'] = Bus('heat output')
        self.buses['heat output'].add_comps(
            {'comp': self.comps['cons'], 'base': 'component'}
        )

        self.nw.add_busses(*[bus for bus in self.buses.values()])

    def init_simulation(self, **kwargs):
        """Perform initial parametrization with starting values."""
        # Components
        self.comps['lp_comp1'].set_attr(eta_s=self.params['lp_comp1']['eta_s'])
        self.comps['hp_comp1'].set_attr(eta_s=self.params['hp_comp1']['eta_s'])
        self.comps['lp_comp2'].set_attr(eta_s=self.params['lp_comp2']['eta_s'])
        self.comps['hp_comp2'].set_attr(eta_s=self.params['hp_comp2']['eta_s'])
        self.comps['hs_pump'].set_attr(eta_s=self.params['hs_pump']['eta_s'])
        self.comps['cons_pump'].set_attr(
            eta_s=self.params['cons_pump']['eta_s']
        )

        self.comps['evap'].set_attr(
            pr1=self.params['evap']['pr1'], pr2=self.params['evap']['pr2']
        )
        self.comps['inter'].set_attr(
            pr1=self.params['inter']['pr1'], pr2=self.params['inter']['pr2']
        )
        self.comps['cond'].set_attr(
            pr1=self.params['cond']['pr1'], pr2=self.params['cond']['pr2']
        )
        self.comps['cons'].set_attr(
            pr=self.params['cons']['pr'], Q=self.params['cons']['Q'],
            dissipative=False
        )
        self.comps['ic1'].set_attr(pr=self.params['ic1']['pr'], dissipative=True)
        self.comps['ic2'].set_attr(pr=self.params['ic2']['pr'], dissipative=True)

        # Connections
        self.T_mid = (self.params['B2']['T'] + self.params['C3']['T']) / 2

        # Starting values
        p_evap1, p_cond1, p_mid1, p_evap2, p_cond2, p_mid2 = self.get_pressure_levels(
            T_evap=self.params['B2']['T'], T_mid=self.T_mid,
            T_cond=self.params['C3']['T']
        )
        self.p_evap1 = p_evap1
        self.p_evap2 = p_evap2
        self.p_mid1 = p_mid1
        self.p_mid2 = p_mid2

        h_s_mid1 = PSI(
            'H', 'P', p_mid1 * 1e5,
            'S', PSI('S', 'Q', 1, 'P', p_evap1 * 1e5, self.wf1),
            self.wf1
        ) * 1e-3
        h_s_mid2 = PSI(
            'H', 'P', p_mid2 * 1e5,
            'S', PSI('S', 'Q', 1, 'P', p_evap2 * 1e5, self.wf2),
            self.wf2
        ) * 1e-3

        # Main cycle
        self.conns['A3'].set_attr(x=self.params['A3']['x'], p=p_evap2)
        self.conns['A0'].set_attr(p=p_cond2, fluid={self.wf2: 1})
        self.conns['A5'].set_attr(p=p_mid2, h=h_s_mid2)
        self.conns['D3'].set_attr(x=self.params['D3']['x'], p=p_evap1)
        self.conns['D0'].set_attr(p=p_cond1, fluid={self.wf1: 1})
        self.conns['D5'].set_attr(p=p_mid1, h=h_s_mid1)
        # Heat source
        self.conns['B1'].set_attr(
            T=self.params['B1']['T'], p=self.params['B1']['p'],
            fluid={self.so: 1}
        )
        self.conns['B2'].set_attr(T=self.params['B2']['T'])
        self.conns['B3'].set_attr(p=self.params['B1']['p'])

        # Heat sink
        self.conns['C3'].set_attr(
            T=self.params['C3']['T'], p=self.params['C3']['p'],
            fluid={self.si: 1}
        )
        self.conns['C1'].set_attr(T=self.params['C1']['T'])

        # Perform initial simulation and unset starting values
        self._solve_model(**kwargs)

        self.conns['A0'].set_attr(p=None)
        self.conns['A3'].set_attr(p=None)
        self.conns['A5'].set_attr(h=None)
        self.conns['D0'].set_attr(p=None)
        self.conns['D3'].set_attr(p=None)
        self.conns['D5'].set_attr(h=None)

    def design_simulation(self, **kwargs):
        """Perform final parametrization and design simulation."""
        self.comps['evap'].set_attr(ttd_l=self.params['evap']['ttd_l'])
        self.comps['cond'].set_attr(ttd_u=self.params['cond']['ttd_u'])
        self.comps['inter'].set_attr(ttd_u=self.params['inter']['ttd_u'])
        self.conns['A3'].set_attr(T=self.T_mid - self.params['inter']['ttd_u'] / 2)

        T_bp1 = PSI('T', 'P', self.conns['D4'].p.val_SI, 'Q', 1, self.wf1) - 273.15
        T_bp2 = PSI('T', 'P', self.conns['A4'].p.val_SI, 'Q', 1, self.wf2) - 273.15

        if abs(T_bp2 - self.conns['A4'].T.val) < abs(self.params['ic2']['dT_ic']):
            self.conns['A5'].set_attr(Td_bp=1)
        else:
            self.conns['A5'].set_attr(
                T=Ref(self.conns['A4'], 1, self.params['ic2']['dT_ic'])
            )
        if abs(T_bp1 - self.conns['D4'].T.val) < abs(self.params['ic1']['dT_ic']):
            self.conns['D5'].set_attr(Td_bp=1)
        else:
            self.conns['D5'].set_attr(
                T=Ref(self.conns['D4'], 1, self.params['ic1']['dT_ic'])
            )

        self._solve_model(**kwargs)

        self.m_design = self.conns['A0'].m.val

        self.cop = (
                abs(self.buses['heat output'].P.val)
                / self.buses['power input'].P.val
        )

    def offdesign_simulation(self, log_simulations=False):
        """Perform offdesign parametrization and simulation."""
        if not self.solved_design:
            raise RuntimeError(
                'Heat pump has not been designed via the "design_simulation" '
                + 'method. Therefore the offdesign simulation will fail.'
            )

        # Parametrization
        self.offdesign_parametrization()

        # Simulation
        print('Using improved offdesign simulation method.')
        self.create_ranges()

        deltaT_hs = (
                self.params['B1']['T']
                - self.params['B2']['T']
        )

        multiindex = pd.MultiIndex.from_product(
            [self.T_hs_ff_range, self.T_cons_ff_range, self.pl_range],
            names=['T_hs_ff', 'T_cons_ff', 'pl']
        )

        results_offdesign = pd.DataFrame(
            index=multiindex, columns=['Q', 'P', 'COP', 'epsilon', 'residual']
        )

        for T_hs_ff in self.T_hs_ff_stablerange:
            self.conns['B1'].set_attr(T=T_hs_ff)
            if T_hs_ff <= 7:
                self.conns['B2'].set_attr(T=2)
            else:
                self.conns['B2'].set_attr(T=T_hs_ff - deltaT_hs)

            for T_cons_ff in self.T_cons_ff_stablerange:
                self.conns['C3'].set_attr(T=T_cons_ff)

                self.T_mid = ((T_hs_ff - deltaT_hs) + T_cons_ff) / 2
                self.conns['A3'].set_attr(
                    T=self.T_mid - self.params['inter']['ttd_u'] / 2
                )
                _, _, p_mid1, _, _, p_mid2 = self.get_pressure_levels(
                    T_evap=T_hs_ff, T_mid=self.T_mid, T_cond=T_cons_ff
                )
                self.conns['A5'].set_attr(p=p_mid2)
                self.conns['D5'].set_attr(p=p_mid1)

                for pl in self.pl_stablerange[::-1]:
                    print(
                        f'### Temp. HS = {T_hs_ff} °C, Temp. Cons = '
                        + f'{T_cons_ff} °C, Partload = {pl * 100} % ###'
                    )
                    self.init_path = None
                    no_init_path = (
                            (T_cons_ff != self.T_cons_ff_range[0])
                            and (pl == self.pl_range[-1])
                    )
                    if no_init_path:
                        self.init_path = os.path.abspath(os.path.join(
                            os.path.dirname(__file__), 'stable',
                            f'{self.subdirname}_init'
                        ))

                    self.comps['cons'].set_attr(Q=None)
                    self.conns['A0'].set_attr(m=pl * self.m_design)

                    try:
                        self.nw.solve(
                            'offdesign', design_path=self.design_path
                        )
                        self.perform_exergy_analysis()
                        failed = False
                    except ValueError:
                        failed = True

                    # Logging simulation
                    if log_simulations:
                        logdirpath = os.path.abspath(os.path.join(
                            os.path.dirname(__file__), 'output', 'logging'
                        ))
                        if not os.path.exists(logdirpath):
                            os.mkdir(logdirpath)
                        logpath = os.path.abspath(os.path.join(
                            logdirpath, f'{self.subdirname}_offdesign_log.csv'
                        ))
                        timestamp = datetime.fromtimestamp(time()).strftime(
                            '%H:%M:%S'
                        )
                        log_entry = (
                                f'{timestamp};{(self.nw.residual[-1] < 1e-3)};'
                                + f'{T_hs_ff:.2f};{T_cons_ff:.2f};{pl:.1f};'
                                + f'{self.nw.residual[-1]:.2e}\n'
                        )
                        if not os.path.exists(logpath):
                            with open(logpath, 'w', encoding='utf-8') as file:
                                file.write(
                                    'Time;converged;Temp HS;Temp Cons;Partload;'
                                    + 'Residual\n'
                                )
                                file.write(log_entry)
                        else:
                            with open(logpath, 'a', encoding='utf-8') as file:
                                file.write(log_entry)

                    if pl == self.pl_range[-1] and self.nw.residual[-1] < 1e-3:
                        self.nw.save(os.path.abspath(os.path.join(
                            os.path.dirname(__file__), 'stable',
                            f'{self.subdirname}_init'
                        )))

                    inranges = (
                            (T_hs_ff in self.T_hs_ff_range)
                            & (T_cons_ff in self.T_cons_ff_range)
                            & (pl in self.pl_range)
                    )
                    idx = (T_hs_ff, T_cons_ff, pl)
                    if inranges:
                        empty_or_worse = (
                                pd.isnull(results_offdesign.loc[idx, 'Q'])
                                or (self.nw.residual[-1]
                                    < results_offdesign.loc[idx, 'residual']
                                    )
                        )
                        if empty_or_worse:
                            if failed:
                                results_offdesign.loc[idx, 'Q'] = np.nan
                                results_offdesign.loc[idx, 'P'] = np.nan
                                results_offdesign.loc[idx, 'epsilon'] = np.nan
                            else:
                                results_offdesign.loc[idx, 'Q'] = abs(
                                    self.buses['heat output'].P.val * 1e-6
                                )
                                results_offdesign.loc[idx, 'P'] = (
                                        self.buses['power input'].P.val * 1e-6
                                )
                                results_offdesign.loc[idx, 'epsilon'] = round(
                                    self.ean.network_data['epsilon'], 3
                                )

                            results_offdesign.loc[idx, 'COP'] = (
                                    results_offdesign.loc[idx, 'Q']
                                    / results_offdesign.loc[idx, 'P']
                            )
                            results_offdesign.loc[idx, 'residual'] = (
                                self.nw.residual[-1]
                            )

        if self.params['offdesign']['save_results']:
            resultpath = os.path.abspath(os.path.join(
                os.path.dirname(__file__), 'output',
                f'{self.subdirname}_partload.csv'
            ))
            results_offdesign.to_csv(resultpath, sep=';')

        self.df_to_array(results_offdesign)

    def get_pressure_levels(self, T_evap, T_mid, T_cond):
        """Calculate evaporation, condensation amd intermediate pressure in bar for both cycles."""
        p_evap1 = PSI(
            'P', 'Q', 1,
            'T', T_evap - self.params['evap']['ttd_l'] + 273.15,
            self.wf1
        ) * 1e-5
        p_cond1 = PSI(
            'P', 'Q', 0,
            'T', T_mid + self.params['inter']['ttd_u'] / 2 + 273.15,
            self.wf1
        ) * 1e-5
        p_mid1 = np.sqrt(p_evap1 * p_cond1)
        p_evap2 = PSI(
            'P', 'Q', 1,
            'T', T_mid - self.params['inter']['ttd_u'] / 2 + 273.15,
            self.wf2
        ) * 1e-5
        p_cond2 = PSI(
            'P', 'Q', 0,
            'T', T_cond + self.params['cond']['ttd_u'] + 273.15,
            self.wf2
        ) * 1e-5
        p_mid2 = np.sqrt(p_evap2 * p_cond2)

        return p_evap1, p_cond1, p_mid1, p_evap2, p_cond2, p_mid2

    def get_plotting_states(self, **kwargs):
        """Generate data of states to plot in state diagram."""
        data = {}
        if kwargs['cycle'] == 1:
            data.update(
                {self.comps['inter'].label:
                     self.comps['inter'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['valve1'].label:
                     self.comps['valve1'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['evap'].label:
                     self.comps['evap'].get_plotting_data()[2]}
            )
            data.update(
                {self.comps['lp_comp1'].label:
                     self.comps['lp_comp1'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['ic1'].label:
                     self.comps['ic1'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['hp_comp1'].label:
                     self.comps['hp_comp1'].get_plotting_data()[1]}
            )
        elif kwargs['cycle'] == 2:
            data.update(
                {self.comps['cond'].label:
                     self.comps['cond'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['valve2'].label:
                     self.comps['valve2'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['inter'].label:
                     self.comps['inter'].get_plotting_data()[2]}
            )
            data.update(
                {self.comps['lp_comp2'].label:
                     self.comps['lp_comp2'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['ic2'].label:
                     self.comps['ic2'].get_plotting_data()[1]}
            )
            data.update(
                {self.comps['hp_comp2'].label:
                     self.comps['hp_comp2'].get_plotting_data()[1]}
            )
        else:
            raise ValueError(
                f'Cycle {kwargs["cycle"]} not defined for heat pump '
                + f"'{self.params['setup']['type']}'."
            )

        for comp in data:
            if 'Compressor' in comp:
                data[comp]['starting_point_value'] *= 0.999999

        return data

    def generate_state_diagram(self, refrig='', diagram_type='logph',
                               legend=True, legend_loc='upper left',
                               return_diagram=False, savefig=True,
                               open_file=True, **kwargs):
        kwargs1 = {}
        kwargs2 = {}
        if 'xlims' in kwargs:
            kwargs1['xlims'] = kwargs['xlims'][0]
            kwargs2['xlims'] = kwargs['xlims'][1]
        if 'ylims' in kwargs:
            kwargs1['ylims'] = kwargs['ylims'][0]
            kwargs2['ylims'] = kwargs['ylims'][1]
        if return_diagram:
            diagram1 = super().generate_state_diagram(
                refrig=self.params['setup']['refrig1'],
                diagram_type=diagram_type, legend=legend,
                legend_loc=legend_loc,
                return_diagram=return_diagram, savefig=savefig,
                open_file=open_file, cycle=1, **kwargs1
            )
            diagram2 = super().generate_state_diagram(
                refrig=self.params['setup']['refrig2'],
                diagram_type=diagram_type, legend=legend,
                legend_loc=legend_loc,
                return_diagram=return_diagram, savefig=savefig,
                open_file=open_file, cycle=2, **kwargs2
            )
            return diagram1, diagram2
        else:
            super().generate_state_diagram(
                refrig=self.params['setup']['refrig1'],
                diagram_type=diagram_type, legend=legend,
                legend_loc=legend_loc,
                return_diagram=return_diagram, savefig=savefig,
                open_file=open_file, cycle=1, **kwargs1
            )
            super().generate_state_diagram(
                refrig=self.params['setup']['refrig2'],
                diagram_type=diagram_type, legend=legend,
                legend_loc=legend_loc,
                return_diagram=return_diagram, savefig=savefig,
                open_file=open_file, cycle=2, **kwargs2
            )

    def check_consistency(self):
        """Perform all necessary checks to protect consistency of parameters."""
        self.check_expansion_into_vapor_liquid_region(
            conn='A1', p=self.p_evap2, wf=self.wf2, pr=1
        )
        self.check_expansion_into_vapor_liquid_region(
            conn='D1', p=self.p_evap1, wf=self.wf1, pr=1
        )

        self.check_mid_temperature(wf=self.wf1)

    def check_mid_temperature(self, wf):
        """Check if the intermediate pressure is below the critical pressure."""
        T_crit = PSI('T_critical', wf) - 273.15
        if self.T_mid > T_crit:
            raise ValueError(
                f'Intermediate temperature of {self.T_mid:1f} °C must be below '
                + f'the  critical temperature of {wf} of {T_crit:.1f} °C'
            )

    def check_expansion_into_vapor_liquid_region(self, conn, p, wf, pr):
        T = self.conns[conn].T.val

        T_sat = PSI('T', 'Q', 0, 'P', p * 1e5, wf) - 273.15
        if 'econ_type' in self.__dict__.keys():
            if self.econ_type == 'closed':
                T_sat = PSI(
                    'T', 'Q', 0, 'P', p * 1e5 / pr,
                    wf) - 273.15

        if T < T_sat:
            raise ValueError(
                f'The temperature of {T:.1f} °C at connection {conn} is lower '
                + f'than the saturation temperature {T_sat} °C at {p:2f} bar. '
                + 'Therefore, the vapor-liquid region can not be reached.'
            )