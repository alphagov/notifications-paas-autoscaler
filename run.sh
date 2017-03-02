#!/bin/bash

export AWS_SECRET_ACCESS_KEY=`echo $VCAP_SERVICES | jq '.["user-provided"]|map(select(.name == "notify-paas-autoscaler"))|.[0].credentials.aws_secret_access_key' -r`
export AWS_ACCESS_KEY_ID=`echo $VCAP_SERVICES | jq '.["user-provided"]|map(select(.name == "notify-paas-autoscaler"))|.[0].credentials.aws_access_key_id' -r`
export CF_USERNAME=`echo $VCAP_SERVICES | jq '.["user-provided"]|map(select(.name == "notify-paas-autoscaler"))|.[0].credentials.cf_username' -r`
export CF_PASSWORD=`echo $VCAP_SERVICES | jq '.["user-provided"]|map(select(.name == "notify-paas-autoscaler"))|.[0].credentials.cf_password' -r`

exec "$@"
