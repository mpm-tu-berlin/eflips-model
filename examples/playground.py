import os

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from datetime import datetime, timedelta
from eflips.model import Scenario, Station
import pytz

from multiprocessing import Pool


def process_depot_station(depot_station, DATABASE_URL):

    with Session(create_engine(DATABASE_URL)) as session:

        scenario = session.query(Scenario).filter(Scenario.id == depot_station.scenario_id).one()
        copy_scenario = scenario.clone(session=session)
        session.expire_all()
        depot_station = session.query(Station).filter(Station.id == depot_station.id,
                                                      Station.scenario == copy_scenario).one()
        scenario.select_one_depot(session, depot_station)

        session.commit()


if __name__ == "__main__":



    DATABASE_URL = os.environ["DATABASE_URL"]
    SCENARIO_ID = 1


    # Get all the start stations
    with Session(create_engine(DATABASE_URL)) as session:
        scenario = session.query(Scenario).filter(Scenario.id == SCENARIO_ID).one()

        first_stations = []
        for rot in scenario.rotations:
            first_station = rot.trips[0].route.departure_station
            if first_station not in first_stations:
                first_stations.append(first_station)




    # Create a pool of worker processes
    NUM_WORKERS = len(first_stations)
    with Pool(NUM_WORKERS) as pool:
        # Use the map method to apply the process_depot_station function to each depot station name in the list
        # pool.map(process_depot_station, [(depot_station, DATABASE_URL) for depot_station in first_stations])
        [pool.apply(process_depot_station, args=(depot_station, DATABASE_URL)) for depot_station in first_stations]
