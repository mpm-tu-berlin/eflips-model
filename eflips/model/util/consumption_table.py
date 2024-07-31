import numpy as np
from matplotlib import pyplot as plt
from typing import Any
import pandas as pd
from itertools import product
from eflips.model import Base


class ConsumptionTable(Base):
    """
    Uses a regression model generated from real world electric bus data to create a consumption table in
    django-simba format (temperature, speed, level of loading, incline, consumption) and exports it into
    the session database.
    """

    def calc_consumption(trip_distance: float, temperature: float, mass: float, duration: float
                         ) -> tuple[float | Any, float | Any]:
        """
        This function calculates the consumption of the trip according to the model of
        Ji, Bie, Zeng, Wang https://doi.org/10.1016/j.commtr.2022.100069
        :param trip_distance: Travelled distance in km
        :param temperature: Average temperature during trip in degrees Celsius
        :param mass: Curb weight + passengers in kg
        :param duration: Trip time in minutes
        :return: Trip energy in kWh
        """

        # Calculate trip energy for traction and BTMS w1
        term = (
                -8.091
                + 0.533 * np.log(trip_distance)
                + 0.78 * np.log(mass)
                + 0.353 * np.log(duration)
                + 0.008 * np.abs(temperature - 23.7)
        )
        w1 = np.exp(term)

        # Calculate trip energy for AC w2
        # TODO: Derive a formula for how t_AC_percent is changing over temperature
        ks = [0.053, 0.11]  # Factor for cooling / heating
        AC_threshold = 20  # Above this temperature: cooling, below: heating
        t_AC_percent = (
            1  # Percentage of how long of the trip heating/cooling is turned ON
        )
        if temperature >= AC_threshold:
            k = ks[0]
        else:
            k = ks[1]
        w2 = k * t_AC_percent * duration

        # Total trip energy
        # TODO: Check why model energy is this low
        correction = 1.5  # Energy seems a bit low compared to other data
        trip_energy = correction * (w1 + w2)
        trip_consumption = trip_energy / trip_distance

        return trip_consumption

    def table_generator():
        """
        Takes VehicleType information to create a consumption table in django-simba format.
        :return:
        """

        # Filter Vehicle Type
        # TODO: Get vehicletype and filter if masses are defined
        # TODO: If no masses are defined use generic masses (how to identify bus type?)

        masses_12m = [10000, 20000]  # Empty mass, max mass
        masses_18m = [19000, 29000]
        masses_doubledecker = [17000, 27000]

        # Get masses & determine Level of Loading
        # TODO: use masses from above
        minimum_mass = 10000
        maximum_mass = 20000

        mass_range = [minimum_mass, maximum_mass]
        mass_step = 100  # kg
        masses = np.arange(mass_range[0], mass_range[1], mass_step)
        delta_mass = mass_range[1] - mass_range[0]
        level_of_loading = 1 / delta_mass * masses - 1

        # Temperatures
        temperature_range = [-20, 40]  # °C
        temperature_step = 1
        temperatures = np.arange(temperature_range[0], temperature_range[1], temperature_step)

        # Speeds
        distance = 10  # fixed value for duration calculation
        speed_range = [5, 60]  # km/h
        speed_step = 1
        speeds = np.arange(speed_range[0], speed_range[1], speed_step)

        # Incline
        incline = 0

        # Calculate consumption
        combinations = list(product(temperatures, speeds, level_of_loading))

        consumption_list = []

        for combo in combinations:
            temp, speed, lol = combo
            duration = distance / speed * 60
            mass = (lol + 1) * delta_mass
            consumption = ConsumptionTable.calc_consumption(distance, temp, mass, duration)
            consumption_list.append(consumption)

        # Create table and return
        consumptionTable = pd.DataFrame(combinations, columns=['t_amb', 'speed', 'level_of_loading'])
        consumptionTable['incline'] = incline
        consumptionTable['consumption_kwh_per_km'] = consumption_list

        return consumptionTable


if __name__ == "__main__":
    print(ConsumptionTable.table_generator())

    # TODO: Add consumptionTable to database
