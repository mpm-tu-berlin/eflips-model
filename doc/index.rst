.. eflips-model documentation master file, created by
   sphinx-quickstart on Mon Nov 27 16:01:20 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to eflips-model's documentation!
========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

How to validate compliance of a database
========================================

The recommended way to validate compliance of a database is to create an instance of the schema and then use the `postgresql-autotoc <https://github.com/cbbrowne/autodoc>`_ tool to generate a list of tables and columns. This list can then be compared to the list of tables and columns in the database. The command to generate an HTML file with the list of tables and columns is:

.. code-block:: bash

   postgresql_autodoc -d $DATABASE -h $HOST -u $USER --password=$PASSWORD -t html -l /usr/share/postgresql-autodoc/ --table=Area,AssocAreaProcess,AssocPlanProcess,AssocRouteStation,AssocVehicleTypeVehicleClass,BatteryType,Depot,Event,Line,Plan,Process,Block,Route,Scenario,Station,StopTime,Trip,Vehicle,VehicleClass,VehicleType

(If new tables are added to the database, the list of tables and columns in the command above must be updated.)

postgresql-autotoc can also generate graphs of the database schema. The command to generate a graph of the database schema is:

.. code-block:: bash

   postgresql_autodoc -d $DATABASE -h $HOST -u $USER --password=$PASSWORD -t neato -l /usr/share/postgresql-autodoc/ --table=Area,AssocAreaProcess,AssocPlanProcess,AssocRouteStation,AssocVehicleTypeVehicleClass,BatteryType,Depot,Event,Line,Plan,Process,Block,Route,Scenario,Station,StopTime,Trip,Vehicle,VehicleClass,VehicleType
   # Manually edit the generated file to add the lines
   #   overlap=false;
   #   splines=true;
   #  below the first line
   neato -Tdf -o schema.pdf $DATABASE.neato

How to remove all simulation results from the database
======================================================

The recommended way to remove all simulation results from the database is to use the following SQL command:

.. code-block:: sql

   UPDATE "Block" set vehicle_id=NULL;
   DELETE FROM "Event";
   DELETE FROM "Vehicle";

   DELETE FROM "AssocPlanProcess";
   DELETE FROM "AssocAreaProcess";
   DELETE FROM "Area";
   DELETE FROM "Depot";
   DELETE FROM "Plan";
   DELETE FROM "Process";
