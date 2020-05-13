# Cloud-computing

SETUP
---------------------------------------------------------------------------------------------------------------

1. Install flask,docker,postman



---------------------------------------------------------------------------------------------------------------
STEPS TO RUN
---------------------------------------------------------------------------------------------------------------


ASSIGNMENT 1:
-------------

1. Goto 'Assignment1' folder and open terminal and execute the following 2 commands.
2. export FLASK_APP=a.py
3. flask run
4. Now open Postman and send the requests to http://127.0.0.1:5000/api/v1/<>



ASSIGNMENT 2:
-------------

1. Goto 'Assignment2' folder and open terminal and execute the following 2 commands.
2. sudo service docker start
3. sudo docker-compose up --build
4. Now open Postman and send the requests to
   - For Users container:  http://127.0.0.1:8080/api/v1/users/<>
   - For Rides container:  http://127.0.0.1:8000/api/v1/rides/<>



ASSIGNMENT 3:
-------------

1. Since this assignment is on Load Balancer, it needs to be run on AWS instances.
2. To run on AWS using ALB first create 2 instances, 1 for rides and the other for users conatiners.
3. Copy the 'rides' and 'users' folders from 'Assignment3' folder and put them into respective instances.
4. Create a Load Balancer in AWS and route api/v1/users to users instance and api/v1/rides to rides instance.
5. Now open the terminal inside folders of each instance.
6. Start the docker using the command 'sudo servcie docker start' in both.
7. Run the conatiners using the command 'sudo docker-compose up --build'
8. Now send the requests using postman.



FINAL PROJECT:
-------------

1. The 'Project' folder has 3 folders - orchestrator,rides and users
2. Create 3 instances and a load balancer. Move the 3 folders to 3 instances.ALB remains same as that of assignment 3.
3. Now start docker in all 3 instances using the command 'sudo service docker start'
4. In rides and Users instance, inside the folder, run the command - 'sudo docker-compose up --build'
5. Now in orchestrator instance, goto /orchestrator/tmp/ folder , and run following commands in terminal:
   - Get wlan0 or eth0 IP address using the command - 'ifconfig'
   - Run docker daemon using the command - 'sudo dockerd -H unix:///var/run/docker.sock -H tcp://<IP>'
   - Now wait till docker daemon is started and then run 'sudo docker-compose up --build'
   






