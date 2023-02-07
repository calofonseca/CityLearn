import math
from typing import List, Mapping, Union
from gym import spaces
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import torch
from citylearn.base import Environment
from citylearn.data import EnergySimulation, CarbonIntensity, Pricing, Weather
from citylearn.dynamics import Dynamics, LSTMDynamics
from citylearn.energy_model import Battery, ElectricHeater, HeatPump, PV, StorageTank
from citylearn.preprocessing import PeriodicNormalization

class Building(Environment):
    def __init__(
        self, energy_simulation: EnergySimulation, weather: Weather, observation_metadata: Mapping[str, bool], action_metadata: Mapping[str, bool], carbon_intensity: CarbonIntensity = None, 
        pricing: Pricing = None, dhw_storage: StorageTank = None, cooling_storage: StorageTank = None, heating_storage: StorageTank = None, electrical_storage: Battery = None, 
        dhw_device: Union[HeatPump, ElectricHeater] = None, cooling_device: HeatPump = None, heating_device: Union[HeatPump, ElectricHeater] = None, pv: PV = None, name: str = None, **kwargs
    ):
        r"""Initialize `Building`.

        Parameters
        ----------
        energy_simulation : EnergySimulation
            Temporal features, cooling, heating, dhw and plug loads, solar generation and indoor environment time series.
        weather : Weather
            Outdoor weather conditions and forecasts time sereis.
        observation_metadata : dict
            Mapping of active and inactive observations.
        action_metadata : dict
            Mapping od active and inactive actions.
        carbon_intensity : CarbonIntensity, optional
            Carbon dioxide emission rate time series.
        pricing : Pricing, optional
            Energy pricing and forecasts time series.
        dhw_storage : StorageTank, optional
            Hot water storage object for domestic hot water.
        cooling_storage : StorageTank, optional
            Cold water storage object for space cooling.
        heating_storage : StorageTank, optional
            Hot water storage object for space heating.
        electrical_storage : Battery, optional
            Electric storage object for meeting electric loads.
        dhw_device : Union[HeatPump, ElectricHeater], optional
            Electric device for meeting hot domestic hot water demand and charging `dhw_storage`.
        cooling_device : HeatPump, optional
            Electric device for meeting space cooling demand and charging `cooling_storage`.
        heating_device : Union[HeatPump, ElectricHeater], optional
            Electric device for meeting space heating demand and charging `heating_storage`.
        pv : PV, optional
            PV object for offsetting electricity demand from grid.
        name : str, optional
            Unique building name.

        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments used to initialize super class.
        """

        self.name = name
        self.energy_simulation = energy_simulation
        self.weather = weather
        self.carbon_intensity = carbon_intensity
        self.pricing = pricing
        self.dhw_storage = dhw_storage
        self.cooling_storage = cooling_storage
        self.heating_storage = heating_storage
        self.electrical_storage = electrical_storage
        self.dhw_device = dhw_device
        self.cooling_device = cooling_device
        self.heating_device = heating_device
        self.pv = pv
        self.observation_metadata = observation_metadata
        self.action_metadata = action_metadata
        self.__observation_epsilon = 0.0 # to avoid out of bound observations
        self.observation_space = self.estimate_observation_space()
        self.action_space = self.estimate_action_space()
        super().__init__(**kwargs)

    @property
    def energy_simulation(self) -> EnergySimulation:
        """Temporal features, cooling, heating, dhw and plug loads, solar generation and indoor environment time series."""

        return self.__energy_simulation

    @property
    def weather(self) -> Weather:
        """Outdoor weather conditions and forecasts time series."""

        return self.__weather

    @property
    def observation_metadata(self) -> Mapping[str, bool]:
        """Mapping of active and inactive observations."""

        return self.__observation_metadata

    @property
    def action_metadata(self) -> Mapping[str, bool]:
        """Mapping od active and inactive actions."""

        return self.__action_metadata

    @property
    def carbon_intensity(self) -> CarbonIntensity:
        """Carbon dioxide emission rate time series."""

        return self.__carbon_intensity

    @property
    def pricing(self) -> Pricing:
        """Energy pricing and forecasts time series."""

        return self.__pricing

    @property
    def dhw_storage(self) -> StorageTank:
        """Hot water storage object for domestic hot water."""

        return self.__dhw_storage

    @property
    def cooling_storage(self) -> StorageTank:
        """Cold water storage object for space cooling."""

        return self.__cooling_storage

    @property
    def heating_storage(self) -> StorageTank:
        """Hot water storage object for space heating."""

        return self.__heating_storage

    @property
    def electrical_storage(self) -> Battery:
        """Electric storage object for meeting electric loads."""

        return self.__electrical_storage

    @property
    def dhw_device(self) -> Union[HeatPump, ElectricHeater]:
        """Electric device for meeting hot domestic hot water demand and charging `dhw_storage`."""

        return self.__dhw_device

    @property
    def cooling_device(self) -> HeatPump:
        """Electric device for meeting space cooling demand and charging `cooling_storage`."""

        return self.__cooling_device

    @property
    def heating_device(self) -> Union[HeatPump, ElectricHeater]:
        """Electric device for meeting space heating demand and charging `heating_storage`."""

        return self.__heating_device

    @property
    def pv(self) -> PV:
        """PV object for offsetting electricity demand from grid."""

        return self.__pv

    @property
    def name(self) -> str:
        """Unique building name."""

        return self.__name

    @property
    def observation_space(self) -> spaces.Box:
        """Agent observation space."""

        return self.__observation_space

    @property
    def action_space(self) -> spaces.Box:
        """Agent action spaces."""

        return self.__action_space

    @property
    def observations(self) -> Mapping[str, float]:
        """Observations at current time step."""

        observations = {}
        data = {
            **{k: v[self.time_step] for k, v in vars(self.energy_simulation).items()},
            **{k: v[self.time_step] for k, v in vars(self.weather).items()},
            **{k: v[self.time_step] for k, v in vars(self.pricing).items()},
            'solar_generation':self.pv.get_generation(self.energy_simulation.solar_generation[self.time_step]),
            **{
                'cooling_storage_soc':self.cooling_storage.soc[self.time_step]/self.cooling_storage.capacity,
                'heating_storage_soc':self.heating_storage.soc[self.time_step]/self.heating_storage.capacity,
                'dhw_storage_soc':self.dhw_storage.soc[self.time_step]/self.dhw_storage.capacity,
                'electrical_storage_soc':self.electrical_storage.soc[self.time_step]/self.electrical_storage.capacity_history[0],
            },
            'net_electricity_consumption': self.__net_electricity_consumption[self.time_step],
            **{k: v[self.time_step] for k, v in vars(self.carbon_intensity).items()},
            'cooling_device_cop': self.cooling_device.get_cop(self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=False),
            'heating_device_cop': self.cooling_device.get_cop(
                self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=True
                    ) if isinstance(self.heating_device, HeatPump) else self.heating_device.efficiency,
            'cooling_demand': self.energy_simulation.cooling_demand[self.time_step],
            'heating_demand': self.energy_simulation.heating_demand[self.time_step],
            'cooling_dry_bulb_temperature_set_point': self.energy_simulation.cooling_dry_bulb_temperature_set_point[self.time_step],
            'heating_dry_bulb_temperature_set_point': self.energy_simulation.heating_dry_bulb_temperature_set_point[self.time_step],
            'cooling_dry_bulb_temperature_delta': abs(self.energy_simulation.cooling_dry_bulb_temperature_set_point[self.time_step] - self.energy_simulation.indoor_dry_bulb_temperature[self.time_step]),
            'heating_dry_bulb_temperature_delta': abs(self.energy_simulation.heating_dry_bulb_temperature_set_point[self.time_step] - self.energy_simulation.indoor_dry_bulb_temperature[self.time_step]),
            'occupant_count': self.energy_simulation.occupant_count[self.time_step],
        }
        observations = {k: data[k] for k in self.active_observations if k in data.keys()}
        unknown_observations = list(set([k for k in self.active_observations]).difference(observations.keys()))
        assert len(unknown_observations) == 0, f'Unkown observations: {unknown_observations}'
        return observations

    @property
    def active_observations(self) -> List[str]:
        """Observations in `observation_metadata` with True value i.e. obeservable."""

        return [k for k, v in self.observation_metadata.items() if v]

    @property
    def active_actions(self) -> List[str]:
        """Actions in `action_metadata` with True value i.e. indicates which storage systems are to be controlled during simulation."""

        return [k for k, v in self.action_metadata.items() if v]

    @property
    def net_electricity_consumption_without_storage_and_pv_emission(self) -> np.ndarray:
        """Carbon dioxide emmission from `net_electricity_consumption_without_storage_and_pv` time series, in [kg_co2]."""

        return (
            self.carbon_intensity.carbon_intensity[0:self.time_step + 1]*self.net_electricity_consumption_without_storage_and_pv
        ).clip(min=0)

    @property
    def net_electricity_consumption_without_storage_and_pv_price(self) -> np.ndarray:
        """net_electricity_consumption_without_storage_and_pv` cost time series, in [$]."""

        return self.pricing.electricity_pricing[0:self.time_step + 1]*self.net_electricity_consumption_without_storage_and_pv

    @property
    def net_electricity_consumption_without_storage_and_pv(self) -> np.ndarray:
        """Net electricity consumption in the absence of flexibility provided by `cooling_storage` and self generation time series, in [kWh]. 
        
        Notes
        -----
        net_electricity_consumption_without_storage_and_pv = `net_electricity_consumption_without_storage` - `solar_generation`
        """

        return self.net_electricity_consumption_without_storage - self.solar_generation

    @property
    def net_electricity_consumption_without_storage_emission(self) -> np.ndarray:
        """Carbon dioxide emmission from `net_electricity_consumption_without_storage` time series, in [kg_co2]."""

        return (self.carbon_intensity.carbon_intensity[0:self.time_step + 1]*self.net_electricity_consumption_without_storage).clip(min=0)

    @property
    def net_electricity_consumption_without_storage_price(self) -> np.ndarray:
        """`net_electricity_consumption_without_storage` cost time series, in [$]."""

        return self.pricing.electricity_pricing[0:self.time_step + 1]*self.net_electricity_consumption_without_storage

    @property
    def net_electricity_consumption_without_storage(self) -> np.ndarray:
        """net electricity consumption in the absence of flexibility provided by storage devices time series, in [kWh]. 
        
        Notes
        -----
        net_electricity_consumption_without_storage = `net_electricity_consumption` - (`cooling_storage_electricity_consumption` + `heating_storage_electricity_consumption` + `dhw_storage_electricity_consumption` + `electrical_storage_electricity_consumption`)
        """

        return self.net_electricity_consumption - np.sum([
            self.cooling_storage_electricity_consumption,
            self.heating_storage_electricity_consumption,
            self.dhw_storage_electricity_consumption,
            self.electrical_storage_electricity_consumption
        ], axis = 0)

    @property
    def net_electricity_consumption_emission(self) -> List[float]:
        """Carbon dioxide emmission from `net_electricity_consumption` time series, in [kg_co2]."""

        return self.__net_electricity_consumption_emission

    @property
    def net_electricity_consumption_price(self) -> List[float]:
        """`net_electricity_consumption` cost time series, in [$]."""

        return self.__net_electricity_consumption_price

    @property
    def net_electricity_consumption(self) -> List[float]:
        """net electricity consumption time series, in [kWh]. 
        
        Notes
        -----
        net_electricity_consumption = `cooling_electricity_consumption` + `heating_electricity_consumption` + `dhw_electricity_consumption` + `electrical_storage_electricity_consumption` + `non_shiftable_load_demand` + `solar_generation`
        """

        return self.__net_electricity_consumption

    @property
    def cooling_electricity_consumption(self) -> List[float]:
        """`cooling_device` net electricity consumption in meeting domestic hot water and `cooling_stoage` energy demand time series, in [kWh]. 
        
        Positive values indicate `cooling_device` electricity consumption to charge `cooling_storage` and/or meet `cooling_demand` while negative values indicate avoided `cooling_device` 
        electricity consumption by discharging `cooling_storage` to meet `cooling_demand`.
        """

        return self.__cooling_electricity_consumption

    @property
    def heating_electricity_consumption(self) -> List[float]:
        """`heating_device` net electricity consumption in meeting domestic hot water and `heating_stoage` energy demand time series, in [kWh]. 
        
        Positive values indicate `heating_device` electricity consumption to charge `heating_storage` and/or meet `heating_demand` while negative values indicate avoided `heating_device` 
        electricity consumption by discharging `heating_storage` to meet `heating_demand`.
        """

        return self.__heating_electricity_consumption

    @property
    def dhw_electricity_consumption(self) -> List[float]:
        """`dhw_device` net electricity consumption in meeting domestic hot water and `dhw_stoage` energy demand time series, in [kWh]. 
        
        Positive values indicate `dhw_device` electricity consumption to charge `dhw_storage` and/or meet `dhw_demand` while negative values indicate avoided `dhw_device` 
        electricity consumption by discharging `dhw_storage` to meet `dhw_demand`.
        """

        return self.__dhw_electricity_consumption

    @property
    def cooling_storage_electricity_consumption(self) -> np.ndarray:
        """`cooling_storage` net electricity consumption time series, in [kWh]. 
        
        Positive values indicate `cooling_device` electricity consumption to charge `cooling_storage` while negative values indicate avoided `cooling_device` 
        electricity consumption by discharging `cooling_storage` to meet `cooling_demand`.
        """

        return self.cooling_device.get_input_power(self.cooling_storage.energy_balance, self.weather.outdoor_dry_bulb_temperature[:self.time_step + 1], False)

    @property
    def heating_storage_electricity_consumption(self) -> np.ndarray:
        """`heating_storage` net electricity consumption time series, in [kWh]. 
        
        Positive values indicate `heating_device` electricity consumption to charge `heating_storage` while negative values indicate avoided `heating_device` 
        electricity consumption by discharging `heating_storage` to meet `heating_demand`.
        """

        if isinstance(self.heating_device, HeatPump):
            consumption = self.heating_device.get_input_power(self.heating_storage.energy_balance, self.weather.outdoor_dry_bulb_temperature[:self.time_step + 1], True)
        else:
            consumption = self.heating_device.get_input_power(self.heating_storage.energy_balance)

        return consumption

    @property
    def dhw_storage_electricity_consumption(self) -> np.ndarray:
        """`dhw_storage` net electricity consumption time series, in [kWh]. 
        
        Positive values indicate `dhw_device` electricity consumption to charge `dhw_storage` while negative values indicate avoided `dhw_device` 
        electricity consumption by discharging `dhw_storage` to meet `dhw_demand`.
        """

        if isinstance(self.dhw_device, HeatPump):
            consumption = self.dhw_device.get_input_power(self.dhw_storage.energy_balance, self.weather.outdoor_dry_bulb_temperature[:self.time_step + 1], True)
        else:
            consumption = self.dhw_device.get_input_power(self.dhw_storage.energy_balance)

        return consumption

    @property
    def electrical_storage_electricity_consumption(self) -> np.ndarray:
        """Energy supply from grid and/or `PV` to `electrical_storage` time series, in [kWh]."""

        return np.array(self.electrical_storage.electricity_consumption, dtype=float)

    @property
    def energy_from_cooling_device_to_cooling_storage(self) -> np.ndarray:
        """Energy supply from `cooling_device` to `cooling_storage` time series, in [kWh]."""

        return np.array(self.cooling_storage.energy_balance, dtype=float).clip(min=0)

    @property
    def energy_from_heating_device_to_heating_storage(self) -> np.ndarray:
        """Energy supply from `heating_device` to `heating_storage` time series, in [kWh]."""

        return np.array(self.heating_storage.energy_balance, dtype=float).clip(min=0)

    @property
    def energy_from_dhw_device_to_dhw_storage(self) -> np.ndarray:
        """Energy supply from `dhw_device` to `dhw_storage` time series, in [kWh]."""

        return np.array(self.dhw_storage.energy_balance, dtype=float).clip(min=0)

    @property
    def energy_to_electrical_storage(self) -> np.ndarray:
        """Energy supply from `electrical_device` to building time series, in [kWh]."""

        return np.array(self.electrical_storage.energy_balance, dtype=float).clip(min=0)

    @property
    def energy_from_cooling_device(self) -> np.ndarray:
        """Energy supply from `cooling_device` to building time series, in [kWh]."""

        return self.cooling_demand - self.energy_from_cooling_storage

    @property
    def energy_from_heating_device(self) -> np.ndarray:
        """Energy supply from `heating_device` to building time series, in [kWh]."""

        return self.heating_demand - self.energy_from_heating_storage

    @property
    def energy_from_dhw_device(self) -> np.ndarray:
        """Energy supply from `dhw_device` to building time series, in [kWh]."""

        return self.dhw_demand - self.energy_from_dhw_storage

    @property
    def energy_from_cooling_storage(self) -> np.ndarray:
        """Energy supply from `cooling_storage` to building time series, in [kWh]."""

        return np.array(self.cooling_storage.energy_balance, dtype=float).clip(max=0)*-1

    @property
    def energy_from_heating_storage(self) -> np.ndarray:
        """Energy supply from `heating_storage` to building time series, in [kWh]."""

        return np.array(self.heating_storage.energy_balance, dtype=float).clip(max=0)*-1

    @property
    def energy_from_dhw_storage(self) -> np.ndarray:
        """Energy supply from `dhw_storage` to building time series, in [kWh]."""

        return np.array(self.dhw_storage.energy_balance, dtype=float).clip(max=0)*-1

    @property
    def energy_from_electrical_storage(self) -> np.ndarray:
        """Energy supply from `electrical_storage` to building time series, in [kWh]."""

        return np.array(self.electrical_storage.energy_balance, dtype=float).clip(max=0)*-1

    @property
    def cooling_demand(self) -> np.ndarray:
        """Space cooling demand to be met by `cooling_device` and/or `cooling_storage` time series, in [kWh]."""

        return self.energy_simulation.cooling_demand[0:self.time_step + 1]

    @property
    def heating_demand(self) -> np.ndarray:
        """Space heating demand to be met by `heating_device` and/or `heating_storage` time series, in [kWh]."""

        return self.energy_simulation.heating_demand[0:self.time_step + 1]

    @property
    def dhw_demand(self) -> np.ndarray:
        """Domestic hot water demand to be met by `dhw_device` and/or `dhw_storage` time series, in [kWh]."""

        return self.energy_simulation.dhw_demand[0:self.time_step + 1]

    @property
    def non_shiftable_load_demand(self) -> np.ndarray:
        """Electricity load that must be met by the grid, or `PV` and/or `electrical_storage` if available time series, in [kWh]."""

        return self.energy_simulation.non_shiftable_load[0:self.time_step + 1]

    @property
    def solar_generation(self) -> np.ndarray:
        """`PV` solar generation (negative value) time series, in [kWh]."""

        return self.__solar_generation[:self.time_step + 1]

    @energy_simulation.setter
    def energy_simulation(self, energy_simulation: EnergySimulation):
        self.__energy_simulation = energy_simulation

    @weather.setter
    def weather(self, weather: Weather):
        self.__weather = weather

    @observation_metadata.setter
    def observation_metadata(self, observation_metadata: Mapping[str, bool]):
        self.__observation_metadata = observation_metadata

    @action_metadata.setter
    def action_metadata(self, action_metadata: Mapping[str, bool]):
        self.__action_metadata = action_metadata

    @carbon_intensity.setter
    def carbon_intensity(self, carbon_intensity: CarbonIntensity):
        if carbon_intensity is None:
            self.__carbon_intensity = CarbonIntensity(np.zeros(len(self.energy_simulation.hour), dtype = float))
        else:
            self.__carbon_intensity = carbon_intensity

    @pricing.setter
    def pricing(self, pricing: Pricing):
        if pricing is None:
            self.__pricing = Pricing(
                np.zeros(len(self.energy_simulation.hour), dtype = float),
                np.zeros(len(self.energy_simulation.hour), dtype = float),
                np.zeros(len(self.energy_simulation.hour), dtype = float),
                np.zeros(len(self.energy_simulation.hour), dtype = float),
            )
        else:
            self.__pricing = pricing

    @dhw_storage.setter
    def dhw_storage(self, dhw_storage: StorageTank):
        self.__dhw_storage = StorageTank(0.0) if dhw_storage is None else dhw_storage

    @cooling_storage.setter
    def cooling_storage(self, cooling_storage: StorageTank):
        self.__cooling_storage = StorageTank(0.0) if cooling_storage is None else cooling_storage

    @heating_storage.setter
    def heating_storage(self, heating_storage: StorageTank):
        self.__heating_storage = StorageTank(0.0) if heating_storage is None else heating_storage

    @electrical_storage.setter
    def electrical_storage(self, electrical_storage: Battery):
        self.__electrical_storage = Battery(0.0, 0.0) if electrical_storage is None else electrical_storage

    @dhw_device.setter
    def dhw_device(self, dhw_device: Union[HeatPump, ElectricHeater]):
        self.__dhw_device = ElectricHeater(0.0) if dhw_device is None else dhw_device

    @cooling_device.setter
    def cooling_device(self, cooling_device: HeatPump):
        self.__cooling_device = HeatPump(0.0) if cooling_device is None else cooling_device

    @heating_device.setter
    def heating_device(self, heating_device: Union[HeatPump, ElectricHeater]):
        self.__heating_device = HeatPump(0.0) if heating_device is None else heating_device

    @pv.setter
    def pv(self, pv: PV):
        self.__pv = PV(0.0) if pv is None else pv

    @observation_space.setter
    def observation_space(self, observation_space: spaces.Box):
        self.__observation_space = observation_space

    @action_space.setter
    def action_space(self, action_space: spaces.Box):
        self.__action_space = action_space

    @name.setter
    def name(self, name: str):
        self.__name = self.uid if name is None else name

    def apply_actions(self, 
        cooling_device_action: float = None, heating_device_action: float = None,
        cooling_storage_action: float = None, heating_storage_action: float = None, 
        dhw_storage_action: float = None, electrical_storage_action: float = None
    ):
        r"""Charge/discharge storage devices.

        Parameters
        ----------
        cooling_device_action : float, default: 0.0
            Fraction of `cooling_device` `nominal_power` to make available for space cooling.
        heating_device_action : float, default: 0.0
            Fraction of `heating_device` `nominal_power` to make available for space heating.
        cooling_storage_action : float, default: 0.0
            Fraction of `cooling_storage` `capacity` to charge/discharge by.
        heating_storage_action : float, default: 0.0
            Fraction of `heating_storage` `capacity` to charge/discharge by.
        dhw_storage_action : float, default: 0.0
            Fraction of `dhw_storage` `capacity` to charge/discharge by.
        electrical_storage_action : float, default: 0.0
            Fraction of `electrical_storage` `capacity` to charge/discharge by.
        """

        cooling_device_action = 0.0 if cooling_device_action is None else cooling_device_action
        heating_device_action = 0.0 if heating_device_action is None else heating_device_action
        cooling_storage_action = 0.0 if cooling_storage_action is None else cooling_storage_action
        heating_storage_action = 0.0 if heating_storage_action is None else heating_storage_action
        dhw_storage_action = 0.0 if dhw_storage_action is None else dhw_storage_action
        electrical_storage_action = 0.0 if electrical_storage_action is None else electrical_storage_action
        self.update_cooling_device(cooling_device_action)
        self.update_heating_device(heating_device_action)
        self.update_cooling_storage(cooling_storage_action)
        self.update_heating_storage(heating_storage_action)
        self.update_dhw_storage(dhw_storage_action)
        self.update_electrical_storage(electrical_storage_action)
        self.update_dynamics()

    def update_dynamics(self):
        r"""Update building dynamics e.g. space indoor temperature.
        """

        return

    def update_cooling_device(self, action: float):
        r"""Update space cooling demand for `cooling_device`.

        Parameters
        ----------
        action : float
            Fraction of `cooling_device` `nominal_power` to make available for space cooling.
        """

        return

    def update_heating_device(self, action: float):
        r"""Update space heating demand for `heating_device`.

        Parameters
        ----------
        action : float
            Fraction of `heating_device` `nominal_power` to make available for space heating.
        """

        return

    def update_cooling_storage(self, action: float):
        r"""Charge/discharge `cooling_storage`.

        Parameters
        ----------
        action : float
            Fraction of `cooling_storage` `capacity` to charge/discharge by.
        """

        energy = action*self.cooling_storage.capacity
        space_demand = self.energy_simulation.cooling_demand[self.time_step]
        space_demand = 0 if space_demand is None or math.isnan(space_demand) else space_demand # case where space demand is unknown
        max_output = self.cooling_device.get_max_output_power(self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=False)
        energy = max(-space_demand, min(max_output - space_demand, energy))
        self.cooling_storage.charge(energy)
        input_power = self.cooling_device.get_input_power(space_demand + energy, self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=False)
        self.cooling_device.update_electricity_consumption(input_power)

    def update_heating_storage(self, action: float):
        r"""Charge/discharge `heating_storage`.

        Parameters
        ----------
        action : float
            Fraction of `heating_storage` `capacity` to charge/discharge by.
        """

        energy = action*self.heating_storage.capacity
        space_demand = self.energy_simulation.heating_demand[self.time_step]
        space_demand = 0 if space_demand is None or math.isnan(space_demand) else space_demand # case where space demand is unknown
        max_output = self.heating_device.get_max_output_power(self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=True)\
            if isinstance(self.heating_device, HeatPump) else self.heating_device.get_max_output_power()
        energy = max(-space_demand, min(max_output - space_demand, energy))
        self.heating_storage.charge(energy)
        demand = space_demand + energy
        input_power = self.heating_device.get_input_power(demand, self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=True)\
            if isinstance(self.heating_device, HeatPump) else self.heating_device.get_input_power(demand)
        self.heating_device.update_electricity_consumption(input_power)

    def update_dhw_storage(self, action: float):
        r"""Charge/discharge `dhw_storage`.

        Parameters
        ----------
        action : float
            Fraction of `dhw_storage` `capacity` to charge/discharge by.
        """

        energy = action*self.dhw_storage.capacity
        space_demand = self.energy_simulation.dhw_demand[self.time_step]
        space_demand = 0 if space_demand is None or math.isnan(space_demand) else space_demand # case where space demand is unknown
        max_output = self.dhw_device.get_max_output_power(self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=True)\
            if isinstance(self.dhw_device, HeatPump) else self.dhw_device.get_max_output_power()
        energy = max(-space_demand, min(max_output - space_demand, energy))
        self.dhw_storage.charge(energy)
        demand = space_demand + energy
        input_power = self.dhw_device.get_input_power(demand, self.weather.outdoor_dry_bulb_temperature[self.time_step], heating=True)\
            if isinstance(self.dhw_device, HeatPump) else self.dhw_device.get_input_power(demand)
        self.dhw_device.update_electricity_consumption(input_power) 

    def update_electrical_storage(self, action: float):
        r"""Charge/discharge `electrical_storage`.

        Parameters
        ----------
        action : float
            Fraction of `electrical_storage` `capacity` to charge/discharge by.
        """

        energy = action*self.electrical_storage.capacity
        self.electrical_storage.charge(energy)

    def estimate_observation_space(self) -> spaces.Box:
        r"""Get estimate of observation spaces.

        Find minimum and maximum possible values of all the observations, which can then be used by the RL agent to scale the observations and train any function approximators more effectively.

        Returns
        -------
        observation_space : spaces.Box
            Observation low and high limits.

        Notes
        -----
        Lower and upper bounds of net electricity consumption are rough estimates and may not be completely accurate hence,
        scaling this observation-variable using these bounds may result in normalized values above 1 or below 0.
        """

        low_limit, high_limit = [], []
        temperature_band = 20 # C
        data = {
            'solar_generation':np.array(self.pv.get_generation(self.energy_simulation.solar_generation)),
            **vars(self.energy_simulation),
            **vars(self.weather),
            **vars(self.carbon_intensity),
            **vars(self.pricing),
        }

        for key in self.active_observations:
            if key == 'net_electricity_consumption':
                net_electric_consumption = self.energy_simulation.non_shiftable_load\
                    + (self.energy_simulation.dhw_demand)\
                        + self.energy_simulation.cooling_demand\
                            + self.energy_simulation.heating_demand\
                                + (self.dhw_storage.capacity/0.8)\
                                    + (self.cooling_storage.capacity/0.8)\
                                        + (self.heating_storage.capacity/0.8)\
                                            + (self.electrical_storage.capacity/0.8)\
                                                - data['solar_generation']
    
                low_limit.append(-max(abs(net_electric_consumption)))
                high_limit.append(max(abs(net_electric_consumption)))

            elif key in ['cooling_storage_soc', 'heating_storage_soc', 'dhw_storage_soc', 'electrical_storage_soc']:
                low_limit.append(0.0)
                high_limit.append(1.0)

            elif key in ['cooling_device_cop']:
                cop = self.cooling_device.get_cop(self.weather.outdoor_dry_bulb_temperature, heating=False)
                low_limit.append(min(cop))
                high_limit.append(max(cop))

            elif key in ['heating_device_cop']:
                if isinstance(self.heating_device, HeatPump):
                    cop = self.heating_device.get_cop(self.weather.outdoor_dry_bulb_temperature, heating=True)
                    low_limit.append(min(cop))
                    high_limit.append(max(cop))
                else:
                    low_limit.append(self.heating_device.efficiency)
                    high_limit.append(self.heating_device.efficiency)

            elif key == 'indoor_dry_bulb_temperature':
                low_limit.append(self.energy_simulation.indoor_dry_bulb_temperature.min() - temperature_band)
                high_limit.append(self.energy_simulation.indoor_dry_bulb_temperature.max() + temperature_band)

            elif key in ['cooling_dry_bulb_temperature_delta', 'heating_dry_bulb_temperature_delta']:
                low_limit.append(0.0)
                high_limit.append(temperature_band)
                
            elif key in ['cooling_demand', 'heating_demand']:
                low_limit.append(0.0)
                energy_simulation = vars(self)[f'_Building__energy_simulation']
                demand = vars(energy_simulation)[key].max()
                high_limit.append(demand*2.5)

            else:
                low_limit.append(min(data[key]))
                high_limit.append(max(data[key]))

        low_limit = [v - self.__observation_epsilon for v in low_limit]
        high_limit = [v + self.__observation_epsilon for v in high_limit]
        return spaces.Box(low=np.array(low_limit, dtype='float32'), high=np.array(high_limit, dtype='float32'))
    
    def estimate_action_space(self) -> spaces.Box:
        r"""Get estimate of action spaces.

        Find minimum and maximum possible values of all the actions, which can then be used by the RL agent to scale the selected actions.

        Returns
        -------
        action_space : spaces.Box
            Action low and high limits.

        Notes
        -----
        The lower and upper bounds for the `cooling_storage`, `heating_storage` and `dhw_storage` actions are set to (+/-) 1/maximum_demand for each respective end use, 
        as the energy storage device can't provide the building with more energy than it will ever need for a given time step. . 
        For example, if `cooling_storage` capacity is 20 kWh and the maximum `cooling_demand` is 5 kWh, its actions will be bounded between -5/20 and 5/20.
        These boundaries should speed up the learning process of the agents and make them more stable compared to setting them to -1 and 1. 
        """
        
        low_limit, high_limit = [], []
 
        for key in self.active_actions:
            if key == 'electrical_storage':
                low_limit.append(-1.0)
                high_limit.append(1.0)

            elif key in ['cooling_device', 'heating_device']:
                low_limit.append(0.0)
                high_limit.append(1.0)
            
            else:
                capacity = vars(self)[f'_Building__{key}'].capacity
                energy_simulation = vars(self)[f'_Building__energy_simulation']
                maximum_demand = vars(energy_simulation)[f'{key.split("_")[0]}_demand'].max()
                maximum_demand_ratio = maximum_demand/capacity

                try:
                    low_limit.append(max(-maximum_demand_ratio, -1.0))
                    high_limit.append(min(maximum_demand_ratio, 1.0))
                except ZeroDivisionError:
                    low_limit.append(-1.0)
                    high_limit.append(1.0)
 
        return spaces.Box(low=np.array(low_limit, dtype='float32'), high=np.array(high_limit, dtype='float32'))

    def autosize_cooling_device(self, **kwargs):
        """Autosize `cooling_device` `nominal_power` to minimum power needed to always meet `cooling_demand`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `cooling_device` `autosize` function.
        """

        self.cooling_device.autosize(self.weather.outdoor_dry_bulb_temperature, cooling_demand = self.energy_simulation.cooling_demand, **kwargs)

    def autosize_heating_device(self, **kwargs):
        """Autosize `heating_device` `nominal_power` to minimum power needed to always meet `heating_demand`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `heating_device` `autosize` function.
        """

        self.heating_device.autosize(self.weather.outdoor_dry_bulb_temperature, heating_demand = self.energy_simulation.heating_demand, **kwargs)\
            if isinstance(self.heating_device, HeatPump) else self.heating_device.autosize(self.energy_simulation.heating_demand, **kwargs)

    def autosize_dhw_device(self, **kwargs):
        """Autosize `dhw_device` `nominal_power` to minimum power needed to always meet `dhw_demand`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `dhw_device` `autosize` function.
        """

        self.dhw_device.autosize(self.weather.outdoor_dry_bulb_temperature, heating_demand = self.energy_simulation.dhw_demand, **kwargs)\
            if isinstance(self.dhw_device, HeatPump) else self.dhw_device.autosize(self.energy_simulation.dhw_demand, **kwargs)

    def autosize_cooling_storage(self, **kwargs):
        """Autosize `cooling_storage` `capacity` to minimum capacity needed to always meet `cooling_demand`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `cooling_storage` `autosize` function.
        """

        self.cooling_storage.autosize(self.energy_simulation.cooling_demand, **kwargs)

    def autosize_heating_storage(self, **kwargs):
        """Autosize `heating_storage` `capacity` to minimum capacity needed to always meet `heating_demand`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `heating_storage` `autosize` function.
        """

        self.heating_storage.autosize(self.energy_simulation.heating_demand, **kwargs)

    def autosize_dhw_storage(self, **kwargs):
        """Autosize `dhw_storage` `capacity` to minimum capacity needed to always meet `dhw_demand`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `dhw_storage` `autosize` function.
        """

        self.dhw_storage.autosize(self.energy_simulation.dhw_demand, **kwargs)

    def autosize_electrical_storage(self, **kwargs):
        """Autosize `electrical_storage` `capacity` to minimum capacity needed to store maximum `solar_generation`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `electrical_storage` `autosize` function.
        """

        self.electrical_storage.autosize(self.pv.get_generation(self.energy_simulation.solar_generation), **kwargs)

    def autosize_pv(self, **kwargs):
        """Autosize `PV` `nominal_pwer` to minimum nominal_power needed to output maximum `solar_generation`.
        
        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `electrical_storage` `autosize` function.
        """

        self.pv.autosize(self.pv.get_generation(self.energy_simulation.solar_generation), **kwargs)

    def next_time_step(self):
        r"""Advance all energy storage and electric devices and, PV to next `time_step`."""

        self.cooling_device.next_time_step()
        self.heating_device.next_time_step()
        self.dhw_device.next_time_step()
        self.cooling_storage.next_time_step()
        self.heating_storage.next_time_step()
        self.dhw_storage.next_time_step()
        self.electrical_storage.next_time_step()
        self.pv.next_time_step()
        super().next_time_step()
        self.update_variables()

    def reset(self):
        r"""Reset `Building` to initial state."""

        # object reset
        super().reset()
        self.cooling_storage.reset()
        self.heating_storage.reset()
        self.dhw_storage.reset()
        self.electrical_storage.reset()
        self.cooling_device.reset()
        self.heating_device.reset()
        self.dhw_device.reset()
        self.pv.reset()

        # variable reset
        self.__cooling_electricity_consumption = []
        self.__heating_electricity_consumption = []
        self.__dhw_electricity_consumption = []
        self.__solar_generation = self.pv.get_generation(self.energy_simulation.solar_generation)*-1
        self.__net_electricity_consumption = []
        self.__net_electricity_consumption_emission = []
        self.__net_electricity_consumption_price = []
        self.update_variables()

    def update_variables(self):
        # cooling electricity consumption
        cooling_demand = self.energy_simulation.cooling_demand[self.time_step] + self.cooling_storage.energy_balance[self.time_step]
        cooling_consumption = self.cooling_device.get_input_power(cooling_demand, self.weather.outdoor_dry_bulb_temperature[self.time_step], False)
        self.__cooling_electricity_consumption.append(cooling_consumption)

        # heating electricity consumption
        heating_demand = self.heating_demand[self.time_step] + self.heating_storage.energy_balance[self.time_step]

        if isinstance(self.heating_device, HeatPump):
            heating_consumption = self.heating_device.get_input_power(heating_demand, self.weather.outdoor_dry_bulb_temperature[self.time_step], True)
        else:
            heating_consumption = self.dhw_device.get_input_power(heating_demand)

        self.__heating_electricity_consumption.append(heating_consumption)

        # dhw electricity consumption
        dhw_demand = self.dhw_demand[self.time_step] + self.dhw_storage.energy_balance[self.time_step]

        if isinstance(self.dhw_device, HeatPump):
            dhw_consumption = self.dhw_device.get_input_power(dhw_demand, self.weather.outdoor_dry_bulb_temperature[self.time_step], True)
        else:
            dhw_consumption = self.dhw_device.get_input_power(dhw_demand)

        self.__dhw_electricity_consumption.append(dhw_consumption)

        # net electricity consumption
        net_electricity_consumption = cooling_consumption \
            + heating_consumption \
                + dhw_consumption \
                    + self.electrical_storage.electricity_consumption[self.time_step] \
                        + self.energy_simulation.non_shiftable_load[self.time_step] \
                            + self.__solar_generation[self.time_step]
        self.__net_electricity_consumption.append(net_electricity_consumption)

        # net electriciy consumption price
        self.__net_electricity_consumption_price.append(net_electricity_consumption*self.pricing.electricity_pricing[self.time_step])

        # net electriciy consumption emission
        self.__net_electricity_consumption_emission.append(max(0, net_electricity_consumption*self.carbon_intensity.carbon_intensity[self.time_step]))

class DynamicsBuilding(Building):
    def __init__(self, *args, dynamics: Dynamics, **kwargs):
        super().__init__(*args, **kwargs)
        self.dynamics = dynamics

class LSTMDynamicsBuilding(DynamicsBuilding):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__ideal_cooling_demand = None
        self.__ideal_heating_demand = None
        self.__ideal_dhw_demand = None
        self.__ideal_indoor_dry_bulb_temperature = None
        self.__set_ideal_variables()
        self.dynamics: LSTMDynamics

    @property
    def ideal_cooling_demand(self):
        return self.__ideal_cooling_demand

    @property
    def ideal_heating_demand(self):
        return self.__ideal_heating_demand

    @property
    def ideal_dhw_demand(self):
        return self.__ideal_dhw_demand

    @property
    def ideal_indoor_dry_bulb_temperature(self):
        return self.__ideal_indoor_dry_bulb_temperature

    def update_dynamics(self):
        # implemented for cooling only for now
        columns = [
            'direct_solar_irradiance', 'outdoor_dry_bulb_temperature', 'occupant_count', 'q_hvac',
            'hour_sin', 'hour_cos', 'day_type_sin', 'day_type_cos', 'month_sin', 'month_cos', 'indoor_dry_bulb_temperature'
        ]
        shape = (self.dynamics.lookback, self.dynamics.input_size)
        model_input = pd.DataFrame(np.zeros(shape), columns=columns)
        
        model_input['q_hvac'] = np.roll(np.concatenate([
            self.energy_simulation.cooling_demand, self.energy_simulation.cooling_demand[-self.dynamics.lookback:],
        ]), self.dynamics.lookback - 1)[self.time_step:self.time_step + self.dynamics.lookback]
        model_input['indoor_dry_bulb_temperature'] = np.roll(np.concatenate([
            self.energy_simulation.indoor_dry_bulb_temperature, self.energy_simulation.indoor_dry_bulb_temperature[-self.dynamics.lookback:],
        ]), self.dynamics.lookback)[self.time_step:self.time_step + self.dynamics.lookback]
        columns.remove('q_hvac')
        columns.remove('indoor_dry_bulb_temperature')
        
        data = {
            **vars(self.energy_simulation),
            **vars(self.weather),
        }

        pn = PeriodicNormalization(0)
        periodic_columns = ['hour', 'day_type', 'month']
        
        for c in periodic_columns:
            values = np.roll(np.concatenate([
                data[c], data[c][-self.dynamics.lookback:],
            ]), self.dynamics.lookback)[self.time_step:self.time_step + self.dynamics.lookback]
            pn.x_max = values.max()
            values = pn*values
            model_input[f'{c}_sin'] = values[0]
            model_input[f'{c}_cos'] = values[1]
            columns.remove(f'{c}_sin')
            columns.remove(f'{c}_cos')

        for c in columns:
            model_input[c] = np.roll(np.concatenate([
                data[c], data[c][-self.dynamics.lookback:],
            ]), self.dynamics.lookback)[self.time_step:self.time_step + self.dynamics.lookback]

        # scale model input
        transformers = []

        for c in model_input.columns:
            if c in self.active_observations:
                ix = self.active_observations.index(c)
                fit_data = [self.observation_space.low[ix], self.observation_space.high[ix]]

            elif '_'.join(c.split('_')[:-1]) in periodic_columns:
                values = data['_'.join(c.split('_')[:-1])]
                pn.x_max = values.max()
                values = pn*values

                if c.split('_')[-1] == 'sin':
                    fit_data = [values[0].min(), values[0].max()]
                else:
                    fit_data = [values[1].min(), values[1].max()]

            elif c == 'q_hvac':
                ix = self.active_observations.index('cooling_demand') 
                fit_data = [self.observation_space.low[ix], self.observation_space.high[ix]]

            else:
                raise Exception(f'Unknown model input: {c}')

            transformers.append(MinMaxScaler().fit(np.array(fit_data).reshape(-1, 1)))
            model_input[c] = transformers[-1].transform(model_input[[c]].values)

        model_input_tensor = torch.tensor(np.array(model_input), dtype=torch.float32)
        model_input_tensor = model_input_tensor[np.newaxis, :, :]
        hidden_list = tuple([h.data for h in self.dynamics.hidden_list])
        indoor_dry_bulb_temperature_norm, hidden_list = self.dynamics(model_input_tensor.float(), hidden_list)
        ix = model_input.columns.tolist().index('indoor_dry_bulb_temperature')
        indoor_dry_bulb_temperature = transformers[ix].inverse_transform(indoor_dry_bulb_temperature_norm.detach().numpy())
        self.energy_simulation.indoor_dry_bulb_temperature[self.time_step] = indoor_dry_bulb_temperature[0][0]
        self.dynamics.hidden_list = hidden_list
        
    def update_cooling_device(self, action: float):
        # need to revist this function implementation because 
        # not sure if the action is a proportion of calculated ideal load or heatpump nominal power
        
        if self.energy_simulation.cooling_device_demand_schedule > 0:
            electric_power = min(action*self.cooling_device.nominal_power, self.cooling_device.nominal_power)
            demand = self.cooling_device.get_max_output_power(
                self.weather.outdoor_dry_bulb_temperature[self.time_step], 
                heating=False, 
                max_electric_power=electric_power
            )
        else:
            demand = 0.0

        self.energy_simulation.cooling_demand[self.time_step] = demand 

    def update_heating_device(self, action: float):
        if self.energy_simulation.heating_device_demand_schedule > 0:
            electric_power = min(action*self.heating_device.nominal_power, self.heating_device.nominal_power)
            demand = self.heating_device.get_max_output_power(
                self.weather.outdoor_dry_bulb_temperature[self.time_step], 
                heating=True,
                max_electric_power=electric_power
            ) if isinstance(self.heating_device, HeatPump) else self.heating_device.get_max_output_power()
        else:
            demand = 0.0

        self.energy_simulation.heating_demand[self.time_step] = demand
        
    def __set_ideal_variables(self):
        self.__ideal_cooling_demand = self.energy_simulation.cooling_demand
        self.__ideal_heating_demand = self.energy_simulation.heating_demand
        self.__ideal_dhw_demand = self.energy_simulation.dhw_demand
        self.__ideal_indoor_dry_bulb_temperature = self.energy_simulation.indoor_dry_bulb_temperature