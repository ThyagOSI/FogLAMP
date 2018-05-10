#!/bin/bash

# It waits until either the requested FogLAMP configuration is created or it reaches the timeout.
while [ true ]
do
    curl -s -X GET http://${FOGLAMP_SERVER}:${FOGLAMP_PORT}/foglamp/category/${1}  | jq '.value'  > /dev/null 2>&1
    result=$?

    if [[ "$result" == "0" ]]
    then
        exit 0
    else
        if [[ $count -le ${RETRY_COUNT} ]]
        then
            sleep 1
            count=$((count+1))
        else
            exit 1
        fi
    fi
done