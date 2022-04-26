# Overview
This is a function designed to interface between the Lodgify rental management software,
and the RemoteLock door management system, to automate the creation and distribution of
time boxed access codes for renters.

It is deployed as a lambda function in AWS, which runs every day.  It will poll the Lodgify
API and get a list of confirmed bookings in the near future.  It then checks all the messages
for that booking, to see if a code has already been sent to the user.

If no code has been sent, it will connect to RemoteLock and create a new guest and a random PIN.
This PIN will only work during the rental period, based on the check in/out dates and the times
configured.

It will then email the renter with the new code, via the Lodify messaging system, using AWS SES to
route the message.


## Requirements
- A Lodify account
- A RemoteLock account
- An AWS account

## Configuration
Most configuration is done via the `lambda_code/config.json` file.
Other configuration is in the `terraform/variables.tf` file.

## Deployment
1. Ensure configuration is complete in the `lambda_code/config.json` file
2. Move to the terraform directory: `cd terraform`
3. Initialize TF: `terraform init`
4. Check the plan: `terraform plan`
5. Run deployment: `terraform apply`