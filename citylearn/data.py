from typing import Iterable
import numpy as np

class EnergySimulation:
    """`Building` `energy_simulation` data class.

    Attributes
    ----------
    month : np.array
        Month time series value ranging from 1 - 12.
    hour : np.array
        Hour time series value ranging from 0 - 23.
    day_type : np.array
        Numeric day of week time series ranging from 1 - 8 where 1 - 7 is Monday - Sunday and 8 is reserved for special days e.g. holiday.
    daylight_savings_status : np.array
        Daylight saving status time series signal of 0 or 1 indicating inactive  or active daylight saving respectively.
    indoor_dry_bulb_temperature : np.array
        Zone volume-weighted average building dry bulb temperature time series in [C].
    average_unment_cooling_setpoint_difference : np.array
        Zone volume-weighted average difference between `indoor_dry_bulb_temperature` and cooling temperature setpoints time series in [C].
    indoor_relative_humidity : np.array
        Zone volume-weighted average building relative humidity time series in [%].
    non_shiftable_load : np.array
        Total building non-shiftable plug and equipment loads time series in [kWh].
    dhw_demand : np.array
        Total building domestic hot water demand time series in [kWh].
    cooling_demand : np.array
        Total building space cooling demand time series in [kWh].
    heating_demand : np.array
        Total building space heating demand time series in [kWh].
    solar_generation : np.array
        Inverter output per 1 kW of PV system time series in [W/kW].
    """

    def __init__(
        self, month: Iterable[int], hour: Iterable[int], day_type: Iterable[int],
        daylight_savings_status: Iterable[int], indoor_dry_bulb_temperature: Iterable[float], average_unmet_cooling_setpoint_difference: Iterable[float], indoor_relative_humidity: Iterable[float], 
        non_shiftable_load: Iterable[float], dhw_demand: Iterable[float], cooling_demand: Iterable[float], heating_demand: Iterable[float],
        solar_generation: Iterable[float]
    ):
        r"""Initialize `EnergySimulation`."""

        self.month = np.array(month, dtype = int)
        self.hour = np.array(hour, dtype = int)
        self.day_type = np.array(day_type, dtype = int)
        self.daylight_savings_status = np.array(daylight_savings_status, dtype = int)
        self.indoor_dry_bulb_temperature = np.array(indoor_dry_bulb_temperature, dtype = float)
        self.average_unmet_cooling_setpoint_difference = np.array(average_unmet_cooling_setpoint_difference, dtype = float)
        self.indoor_relative_humidity = np.array(indoor_relative_humidity, dtype = float)
        self.non_shiftable_load = np.array(non_shiftable_load, dtype = float)
        self.dhw_demand = np.array(dhw_demand, dtype = float)
        self.cooling_demand = np.array(cooling_demand, dtype = float)
        self.heating_demand = np.array(heating_demand, dtype = float)
        self.solar_generation = np.array(solar_generation, dtype = float)

class Weather:
    """`Building` `weather` data class.

    Attributes
    ----------
    outdoor_dry_bulb_temperature : np.array
        Outdoor dry bulb temperature time series in [C].
    outdoor_relative_humidity : np.array
        Outdoor relative humidity time series in [%].
    diffuse_solar_irradiance : np.array
        Diffuse solar irradiance time series in [W/m^2].
    direct_solar_irradiance : np.array
        Direct solar irradiance time series in [W/m^2].
    outdoor_dry_bulb_temperature_predicted_6h : np.array
        Outdoor dry bulb temperature 6 hours ahead prediction time series in [C].
    outdoor_dry_bulb_temperature_predicted_12h : np.array
        Outdoor dry bulb temperature 12 hours ahead prediction time series in [C].
    outdoor_dry_bulb_temperature_predicted_24h : np.array
        Outdoor dry bulb temperature 24 hours ahead prediction time series in [C].
    outdoor_relative_humidity_predicted_6h : np.array
        Outdoor relative humidity 6 hours ahead prediction time series in [%].
    outdoor_relative_humidity_predicted_12h : np.array
        Outdoor relative humidity 12 hours ahead prediction time series in [%].
    outdoor_relative_humidity_predicted_24h : np.array
        Outdoor relative humidity 24 hours ahead prediction time series in [%].
    diffuse_solar_irradiance_predicted_6h : np.array
        Diffuse solar irradiance 6 hours ahead prediction time series in [W/m^2].
    diffuse_solar_irradiance_predicted_12h : np.array
        Diffuse solar irradiance 12 hours ahead prediction time series in [W/m^2].
    diffuse_solar_irradiance_predicted_24h : np.array
        Diffuse solar irradiance 24 hours ahead prediction time series in [W/m^2].
    direct_solar_irradiance_predicted_6h : np.array
        Direct solar irradiance 6 hours ahead prediction time series in [W/m^2].
    direct_solar_irradiance_predicted_12h : np.array
        Direct solar irradiance 12 hours ahead prediction time series in [W/m^2].
    direct_solar_irradiance_predicted_24h : np.array
        Direct solar irradiance 24 hours ahead prediction time series in [W/m^2].
    """

    def __init__(
        self, outdoor_dry_bulb_temperature: Iterable[float], outdoor_relative_humidity: Iterable[float], diffuse_solar_irradiance: Iterable[float], direct_solar_irradiance: Iterable[float], 
        outdoor_dry_bulb_temperature_predicted_6h: Iterable[float], outdoor_dry_bulb_temperature_predicted_12h: Iterable[float], outdoor_dry_bulb_temperature_predicted_24h: Iterable[float],
        outdoor_relative_humidity_predicted_6h: Iterable[float], outdoor_relative_humidity_predicted_12h: Iterable[float], outdoor_relative_humidity_predicted_24h: Iterable[float],
        diffuse_solar_irradiance_predicted_6h: Iterable[float], diffuse_solar_irradiance_predicted_12h: Iterable[float], diffuse_solar_irradiance_predicted_24h: Iterable[float],
        direct_solar_irradiance_predicted_6h: Iterable[float], direct_solar_irradiance_predicted_12h: Iterable[float], direct_solar_irradiance_predicted_24h: Iterable[float],
    ):
        r"""Initialize `Weather`."""

        self.outdoor_dry_bulb_temperature = np.array(outdoor_dry_bulb_temperature, dtype = float)
        self.outdoor_relative_humidity = np.array(outdoor_relative_humidity, dtype = float)
        self.diffuse_solar_irradiance = np.array(diffuse_solar_irradiance, dtype = float)
        self.direct_solar_irradiance = np.array(direct_solar_irradiance, dtype = float)
        self.outdoor_dry_bulb_temperature_predicted_6h = np.array(outdoor_dry_bulb_temperature_predicted_6h, dtype = float)
        self.outdoor_dry_bulb_temperature_predicted_12h = np.array(outdoor_dry_bulb_temperature_predicted_12h, dtype = float)
        self.outdoor_dry_bulb_temperature_predicted_24h = np.array(outdoor_dry_bulb_temperature_predicted_24h, dtype = float)
        self.outdoor_relative_humidity_predicted_6h = np.array(outdoor_relative_humidity_predicted_6h, dtype = float)
        self.outdoor_relative_humidity_predicted_12h = np.array(outdoor_relative_humidity_predicted_12h, dtype = float)
        self.outdoor_relative_humidity_predicted_24h = np.array(outdoor_relative_humidity_predicted_24h, dtype = float)
        self.diffuse_solar_irradiance_predicted_6h = np.array(diffuse_solar_irradiance_predicted_6h, dtype = float)
        self.diffuse_solar_irradiance_predicted_12h = np.array(diffuse_solar_irradiance_predicted_12h, dtype = float)
        self.diffuse_solar_irradiance_predicted_24h = np.array(diffuse_solar_irradiance_predicted_24h, dtype = float)
        self.direct_solar_irradiance_predicted_6h = np.array(direct_solar_irradiance_predicted_6h, dtype = float)
        self.direct_solar_irradiance_predicted_12h = np.array(direct_solar_irradiance_predicted_12h, dtype = float)
        self.direct_solar_irradiance_predicted_24h = np.array(direct_solar_irradiance_predicted_24h, dtype = float)

class CarbonIntensity:
    """`Building` `carbon_intensity` data class.

    Attributes
    ----------
    carbon_intensity : np.array
        Outdoor dry bulb temperature time series in [kg_co2/kWh].
    """

    def __init__(self, carbon_intensity: Iterable[float]):
        r"""Initialize `CarbonIntensity`."""

        self.carbon_intensity = np.array(carbon_intensity, dtype = float)