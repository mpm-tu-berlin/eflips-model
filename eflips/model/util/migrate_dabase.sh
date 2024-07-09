#!/bin/sh

# This script takes a given database dump as an argument, loads it into a database, and then runs the migrations on it.
# The dump is then exported to a new file.

### THIS WILL DELETE ALL DATA IN THE DATABASE ###

# Ensure the correct environment variables are set (either DATABASE URL (which gets split into the other variables) or the individual variables)
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL is not set"
  if [ -z "$DATABASE_USER" ]; then
    echo "DATABASE_USER is not set"
    exit 1
  fi

  if [ -z "$DATABASE_PASSWORD" ]; then
    echo "DATABASE_PASSWORD is not set"
    exit 1
  fi

  if [ -z "$DATABASE_NAME" ]; then
    echo "DATABASE_NAME is not set"
    exit 1
  fi
else
  DATABASE_URL_FOR_PARSING=$(echo $DATABASE_URL | sed 's/postgresql:\/\///')
  DATABASE_USER=$(echo $DATABASE_URL_FOR_PARSING | cut -d ':' -f 1)
  DATABASE_PASSWORD=$(echo $DATABASE_URL_FOR_PARSING | cut -d '@' -f 1)
  DATABASE_NAME=$(echo $DATABASE_URL_FOR_PARSING | cut -d '/' -f 2)
fi


# Read in the arguments. They are -i for the input file, -o for the output file
while getopts i:o: flag
do
    case "${flag}" in
        i) input_file=${OPTARG};;
        o) output_file=${OPTARG};;
    esac
done

# Check if the input file exists
if [ ! -f "$input_file" ]; then
  echo "Input file does not exist"
  exit 1
fi

# Load the dump into the database (clearing it first)
psql -U $DATABASE_USER -d $DATABASE_NAME -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
# Re-enable the extensions
psql -U $DATABASE_USER -d $DATABASE_NAME -c "CREATE EXTENSION IF NOT EXISTS \"btree_gist\";"
psql -U $DATABASE_USER -d $DATABASE_NAME -c "CREATE EXTENSION IF NOT EXISTS \"postgis\";"

# Load the dump into the database
# zstd or xz depending on the compression used
zstd -d -c $input_file | psql -U $DATABASE_USER -d $DATABASE_NAME


# Run the migrations (here, the alembic command needs to be run in the directory on level above the one where this script is located)
PWD=$(pwd)
cd $(dirname $0)/..
alembic upgrade head
cd $PWD

# Export the database to a new file
pg_dump -U $DATABASE_USER -d $DATABASE_NAME -Fp --no-owner --no-acl | zstd -T0 -19 --verbose > $output_file
