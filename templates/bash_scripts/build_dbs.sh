#! /bin/bash


db_mipmap={{ mipmap_db }}
db_capture={{ capture_db }}
db_harmonized={{ harmonize_db }}
container_name={{ container_name }} # <update with postgres name container>
db_user={{ db_user }}

if [ -z $1 ]; then
    echo "No Argument given. Exiting...."
    exit 1

elif [ $1 = "all" ]; then
    echo "Creating all ehr datafactory database"
    # create mipmap database
    echo "Creating $db_mipmap database"
    docker exec -it $container_name psql -U $db_user -d postgres -c "DROP DATABASE IF EXISTS $db_mipmap;"
    docker exec -it $container_name psql -U $db_user -d postgres -c "CREATE DATABASE $db_mipmap;"
    # create and set up capture database
    echo "Creating $db_capture database"
    docker exec -it $container_name psql -U $db_user -d postgres -c "DROP DATABASE IF EXISTS $db_capture;"
    docker exec -it $container_name psql -U $db_user -d postgres -c "CREATE DATABASE $db_capture;"
    echo "Setting up $db_capture database"
    docker-compose run --rm i2b2_setup
    # create and set up harmonized database
    echo "Creating $db_harmonized database"
    docker exec -it $container_name psql -U $db_user -d postgres -c "DROP DATABASE IF EXISTS $db_harmonized;"
    docker exec -it $container_name psql -U $db_user -d postgres -c "CREATE DATABASE $db_harmonized;"
    echo "Setting up $db_harmonized database"
    docker-compose run --rm i2b2_setup_harmonized

elif [ $1 = "mipmap" ]; then
# create mipmap database
    echo "Creating $db_mipmap database"
    docker exec -it $container_name psql -U $db_user -d postgres -c "DROP DATABASE IF EXISTS $db_mipmap;"
    docker exec -it $container_name psql -U $db_user -d postgres -c "CREATE DATABASE $db_mipmap;"

elif [ $1 = "capture" ]; then
# create and set up capture database
    echo "Creating $db_capture database"
    docker exec -it $container_name psql -U $db_user -d postgres -c "DROP DATABASE IF EXISTS $db_capture;"
    docker exec -it $container_name psql -U $db_user -d postgres -c "CREATE DATABASE $db_capture;"
    echo "Setting up $db_capture database"
    docker-compose run --rm i2b2_setup

elif [ $1 = "harmonize" ]; then
# create and set up harmonized database
    echo "Creating $db_harmonized database"
    docker exec -it $container_name psql -U $db_user -d postgres -c "DROP DATABASE IF EXISTS $db_harmonized;"
    docker exec -it $container_name psql -U $db_user -d postgres -c "CREATE DATABASE $db_harmonized;"
    echo "Setting up $db_harmonized database"
    docker-compose run --rm i2b2_setup_harmonized
fi
