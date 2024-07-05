import numpy as np
from matplotlib import pyplot as plt
from typing import Any


def calc_tripenergy(
    trip_distance: float, temperature: float, mass: float, duration: float
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
        0.5  # Percentage of how long of the trip heating/cooling is turned ON
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

    return trip_energy, trip_consumption


if __name__ == "__main__":
    TRIP_DISTANCE = 10  # Fix it, then sweep the duration for different average speeds

    MINIMUM_TEMPERATURE = -10  # degrees Celsius
    MAXIMUM_TEMPERATURE = 40
    TEMPERATURE_STEP = 1
    temperatures = np.arange(MINIMUM_TEMPERATURE, MAXIMUM_TEMPERATURE, TEMPERATURE_STEP)

    MINIMUM_MASS = 10000  # Has to be curb weight + passengers
    MAXIMUM_MASS = 20000  # kg
    MASS_STEP = 100
    masses = np.arange(MINIMUM_MASS, MAXIMUM_MASS, MASS_STEP)

    MINIMUM_SPEED = 5  # km/h
    MAXIMUM_SPEED = 50
    SPEED_STEP = 1
    minimum_duration = (TRIP_DISTANCE / MAXIMUM_SPEED) * 60  # minutes
    maximum_duration = (TRIP_DISTANCE / MINIMUM_SPEED) * 60
    durations = np.arange(minimum_duration, maximum_duration, SPEED_STEP)

    energy = np.zeros((len(temperatures), len(masses), len(durations)))
    consumption = np.zeros((len(temperatures), len(masses), len(durations)))

    for i, temperature in enumerate(temperatures):
        for j, mass in enumerate(masses):
            for k, duration in enumerate(durations):
                energy[i, j, k], consumption[i, j, k] = calc_tripenergy(
                    TRIP_DISTANCE, temperature, mass, duration
                )

    # Do a 2d plot of the consumption, for a fixed mass in the middle of the range
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    X, Y = np.meshgrid(temperatures, durations)
    ax.view_init(elev=30, azim=45, roll=0)
    ax.plot_surface(
        X, Y, consumption[:, len(masses) // 2, :].transpose(), cmap="viridis"
    )
    ax.set_ylabel(r"Speed $\frac{km}{h}$")
    # Make the y labels based on speed, not duration
    total_label_count = 8
    speeds = np.linspace(MINIMUM_SPEED, MAXIMUM_SPEED, total_label_count)[::-1]
    durations_for_ticks = np.linspace(0, len(durations), total_label_count)
    ax.set_yticks(durations_for_ticks)
    ax.set_yticklabels([f"{speed:.0f}" for speed in speeds])

    ax.set_xlabel("Temperature °C")
    ax.set_zlabel(r"Consumption $\frac{kWh}{km}$")
    ax.set_title("Using the model of Ji et. al (2022)")
    plt.suptitle("Energy consumption 15-ton electric bus")
    plt.tight_layout()
    plt.savefig("consumption_lut.png")
    plt.savefig("consumption_lut.pdf")
    plt.show()
