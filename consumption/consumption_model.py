import numpy as np
def calc_tripenergy(trip_distance: float, temperature: float, mass: float, duration: float) -> tuple[
    float | Any, float | Any]:
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
    term = (-8.091 + 0.533 * np.log(trip_distance) + 0.78 * np.log(mass) + 0.353 * np.log(duration)
            + 0.008 * np.abs(temperature - 23.7))
    w1 = np.exp(term)

    # Calculate trip energy for AC w2
    # TODO: Derive a formula for how t_AC_percent is changing over temperature
    k = [0.053, 0.11]                   # Factor for cooling / heating
    AC_threshold = 20                   # Above this temperature: cooling, below: heating
    t_AC_percent = 0.5                  # Percentage of how long of the trip heating/cooling is turned ON
    if temperature >= AC_threshold:
        k = k[0]
    else:
        k = k[1]
    w2 = k*t_AC_percent*duration

    # Total trip energy
    # TODO: Check why model energy is this low
    correction = 1.5                    # Energy seems a bit low compared to other data
    trip_energy = correction * (w1 + w2)
    trip_consumption = trip_energy/trip_distance

    return trip_energy, trip_consumption