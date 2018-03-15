# -*- coding: utf-8 -*-
"""
Created on Mon Feb 12 15:08:04 2018

@author: user
"""

#!/usr/bin/env python

import rospy
import cv2, cv_bridge
import numpy as np
import operator
from sensor_msgs.msg import Image, LaserScan
from geometry_msgs.msg import Twist
from pprint import pformat
from tf_conversions import transformations
from math import pi
import matplotlib.pyplot as plt
from nav_msgs.msg import Odometry
from math import radians
import sys

class Follower:

    def __init__(self):
        self.bridge = cv_bridge.CvBridge()
        cv2.namedWindow("window", 1)
        cv2.namedWindow("explored", 1)
        cv2.namedWindow("mask", 1)        
        self.image_sub = rospy.Subscriber("turtlebot/camera/rgb/image_raw", Image, self.callback)
        self.image_depth = rospy.Subscriber("turtlebot/scan", LaserScan, self.depthcallback)
        self.image_odom = rospy.Subscriber("/turtlebot/odom", Odometry, self.explorecallback)         
        self.cmd_vel_pub = rospy.Publisher("turtlebot/cmd_vel", Twist, queue_size=1)
        self.twist = Twist()
        self.centrePointX = 0
        self.centrePointY = 0
        self.depth = 0
        self.dataranges = 0
        self.firstDepthTime = True
        self.firstTime = True
        self.explored = np.zeros((1500, 1500))
        self.found = False
        self.commandChanges = 0
        self.search = False
        self.command = ""
        self.seek = False
        self.founditer = 0
        self.searchtimes = 0 
        self.maskGreen = 0
        self.maskRed = 0
        self.maskYellow = 0
        self.maskBlue = 0
        self.spinTimes = 0
        self.mask = self.maskGreen + self.maskRed + self.maskYellow + self.maskBlue
        self.colors = ["red", "green", "yellow", "blue"] 
        
    
        
    def depthcallback(self, data):
        # Return is a raw value of closeness to bot - 0 being far away, 255 being super close
        
        #NewImg = self.bridge.imgmsg_to_cv2(data.ranges,"passthrough")
        #depth_array = np.array(NewImg, dtype=np.float32)
        #cv2.normalize(depth_array, depth_array, 0, 1, cv2.NORM_MINMAX)
        self.dataranges = data
        if not self.centrePointX == 0:
            if str(self.depth) == "nan":
                self.depth = 10
            else:
                self.depth = data.ranges[self.centrePointX]
        else:
            if str(self.depth) == "nan":
                self.depth = 10
            else:
                self.depth = data.ranges[320]
                
        self.right  = min(self.dataranges.ranges[:320]) + np.nanmean(self.dataranges.ranges[260:380])
        self.left   = min(self.dataranges.ranges[320:]) + np.nanmean(self.dataranges.ranges[320:380])
        
        self.firstDepthTime = False
        #cv2.imshow("depth", depth_array)
        cv2.waitKey(1)
        #cv2.imwrite("depth.png", depth_array*255)

    def callback(self, msg):
        image = self.bridge.imgmsg_to_cv2(msg,desired_encoding='bgr8')
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_green = np.array([ 45, 100,  50])
        upper_green = np.array([ 75, 255, 255])
        
        lower_red = np.array([ 0, 200,  100])
        upper_red = np.array([ 5, 255, 255])
        
        lower_yellow = np.array([ 20, 200,  100])
        upper_yellow = np.array([ 50, 255, 195])
        
        lower_blue = np.array([100, 150, 50])
        upper_blue = np.array([150, 255, 255])
        
        self.maskGreen  = cv2.inRange(hsv, lower_green,  upper_green)
        self.maskRed    = cv2.inRange(hsv, lower_red,    upper_red)
        self.maskYellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
        self.maskBlue   = cv2.inRange(hsv, lower_blue,   upper_blue)
        
        self.MG = cv2.moments(self.maskGreen)['m00']
        self.MR = cv2.moments(self.maskRed)['m00']
        self.MY = cv2.moments(self.maskYellow)['m00']
        self.MB = cv2.moments(self.maskBlue)['m00']        
        
        self.mask = None
        if "red" in self.colors:
            if self.mask == None:
                self.mask = self.maskRed
            self.mask += self.maskRed
        if "yellow" in self.colors:
            if self.mask == None:
                self.mask = self.maskYellow
            self.mask += self.maskYellow
        if "green" in self.colors:
            if self.mask == None:
                self.mask = self.maskGreen
            self.mask += self.maskGreen
        if "blue" in self.colors:
            if self.mask == None:
                self.mask = self.maskBlue
            self.mask += self.maskBlue
            
        h, w, d = image.shape
    
        # calculate the area of the values that are within the mask
        M = cv2.moments(self.mask)
        
        #cv2.imshow("window", image)
        #cv2.imshow("mask", self.mask)
        
        mydepth = self.explore()  
        if not self.firstDepthTime:
            if M['m00'] > 100000:
                if self.depth < 0.75 and M['m00'] > 10000000:
                     self.foundmode(image, M)
                else:
                     self.seekmode(image, M)
            else:
                self.searchmode(image, self.mask)
        

    def odom_orientation(self, q):
        y, p, r = transformations.euler_from_quaternion([q.w, q.x, q.y, q.z])
        return y * 180 / pi
        
    def explorecallback(self, data):
        # NORMALISE TO ZERO AT START FOR DATA EASE
        x = int(data.pose.pose.position.x * 100)
        y = int(data.pose.pose.position.x * 100)        
        if self.firstTime:
            self.diffToStart = [x-500, y-500]
            self.firstTime = False
        
        self.x = x - self.diffToStart[0]
        self.y = y - self.diffToStart[1]
        self.currentPos = [self.x, self.y]
        self.angle = int(self.odom_orientation(data.pose.pose.orientation))
        
        
        
        cv2.imshow("explored", self.threshed)
        cv2.waitKey(1)
        
    def explore(self):
        if str(self.depth) == "nan":
            return
        else:
            depth = int(abs(self.depth)*10)
        
        
        #RIGHT
        if self.angle < -155 or self.angle > 155:
            endPos = [self.x + depth , self.y]
            direction="RIGHT"
        #RIGHT - UP
        elif self.angle in range(115, 155):
            endPos = [self.x + depth, self.y + depth]
            direction="RIGHT - UP"
        #UP
        elif self.angle in range(65, 115):
            endPos = [self.x, self.y + depth]
            direction="UP"
        #LEFT - UP
        elif self.angle in range(25, 65):
            endPos = [self.x - depth, self.y + depth]
            direction="LEFT - UP"
        #LEFT
        elif self.angle in range (-25, 25):
            endPos = [self.x - depth, self.y]
            direction="LEFT"
        #DOWN - LEFT
        elif self.angle in range(-65, -25):
            endPos = [self.x - depth, self.y - depth]
            direction="DOWN - LEFT"
        #DOWN
        elif self.angle in range(-115, -65):
            endPos = [self.x, self.y - depth]
            direction="DOWN"
        #DOWN - RIGHT
        elif self.angle in range(-155, -115):
            endPos = [self.x + depth, self.y - depth]
            direction="DOWN - RIGHT"
        else:
            endPos = [self.x, self.y]
            direction="ERR"            

        print("depth: ", depth)
        #print("currentPos: %", self.currentPos)
        #print("endPos: ", endPos)
        #print("angle: %f direction %s" % (self.angle, direction))
        #print("diff: %i %i" % (self.diffToStart[0], self.diffToStart[1]))
        #self.twist.linear.x = 0.0
        #self.twist.angular.z = 0.0
        #self.cmd_vel_pub.publish(self.twist)
        
        if abs(endPos[0] - self.currentPos[0]) and abs(endPos[0] - self.currentPos[0]) < 2:
            print("AUTO MOVING, DONT WANT TO GO BACK TO ORIGINAL")
            self.commandmoveleft("AUTO MOVING")
            rospy.sleep(5)
        
        if endPos[0] > self.currentPos[0]:
            iterableX = range(self.currentPos[0], endPos[0]+1)
        else:
            iterableX = range(self.currentPos[0], endPos[0]-1,  -1)
        
        if endPos[1] > self.currentPos[1]:
            iterableY = range(self.currentPos[1], endPos[1]+1)
        else:
            iterableY = range(self.currentPos[1], endPos[1]-1, -1)
        
        for x1 in iterableX:
            for y1 in iterableY:
                
                if x1 == endPos[0] and y1 == endPos[1]:
                    if not self.explored[x1, y1] > 0: 
                        self.explored[x1, y1] = 255
                        print("highest at", x1, y1)
                        
                   # self.explored[x1, y1] = 255 # To signify a wall
                    #print("Found wall at", x1, y1)
                else:
                    if not self.explored[x1, y1] > 0 and x1 != y1: 
                        self.explored[x1+1, y1] = 10
                        self.explored[x1, y1] = 10
                        self.explored[x1-1, y1] = 10
                        self.alreadyExplored = False
                        print("Explored at", x1, y1)
                if self.explored[x1, y1] > 0:
                    self.alreadyExplored = True
        im = np.array(self.explored, dtype = np.uint8)
        self.threshed = cv2.adaptiveThreshold(im, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 3, 0)
        return depth
        #self.twist.linear.x = 0.0
        #self.twist.angular.z = 0.1 
        #self.cmd_vel_pub.publish(self.twist)
        
    def commandmoveleft(self, name, recordChanges = False):
        print name
        if recordChanges:
            if not self.command == name:
                self.command == name
                self.commandChanges += 1
        self.twist.angular.z = 0.4
        self.cmd_vel_pub.publish(self.twist)
            
    def commandmoveright(self, name, recordChanges = False):
        print name
        if recordChanges:
            if not self.command == name:
                self.command == name
                self.commandChanges += 1
        self.twist.angular.z = -0.4
        self.cmd_vel_pub.publish(self.twist)
        
    def autocontrolbot(self, seekMode = False):
        self.twist.linear.x = 0.0
        print str(self.commandChanges)
        if self.commandChanges > 50:
            self.commandmoveleft("force move left", True)
        elif abs(self.right-self.left) < 0.5:
            if seekMode:
                self.right  = max(self.dataranges.ranges[:320]) + np.nanmean(self.dataranges.ranges[260:380])
                self.left   = max(self.dataranges.ranges[320:]) + np.nanmean(self.dataranges.ranges[320:380])
                self.autocontrolbot(seekMode = True)
            else:
                self.commandmoveleft("auto move left", True)
        elif str(self.left) == "nan":
            self.commandmoveleft("moving left", True)
        elif str(self.right) == "nan":
            self.commandmoveright("moving right", True)
        elif self.left > self.right:
            self.commandmoveleft("moving left", True)
        else:
            self.commandmoveright("moving right", True)
        self.cmd_vel_pub.publish(self.twist)
        
    def searchmode(self, image, mask):
        if self.search == False:
            print "entering searchmode"
        self.search = True
        self.seek = False
        self.found = False
        self.searchtimes +=1
        self.spinTimes += 1
        
        if self.spinTimes < 200:
            self.twist.linear.x = 0.0
            self.twist.angular.z = 0.3
            self.cmd_vel_pub.publish(self.twist)
        else:
            if min(self.dataranges.ranges) > 0.75:
                self.commandChanges = 0
                self.twist.linear.x = 0.5
                
                if np.nanmean(self.dataranges.ranges[260:380]) > 6.0:
                    self.twist.angular.z = 0.0
                    self.cmd_vel_pub.publish(self.twist)
                else:
                    if abs(self.right-self.left) < 0.2:
                        self.commandmoveright("over auto move right")
                    elif str(self.left) == "nan":
                        self.commandmoveleft("max move left")
                    elif str(self.right) == "nan":
                        self.commandmoveright("max move right")
                    elif self.left > self.right:
                        self.commandmoveleft("over moving left")
                    else:
                        self.commandmoveright("over moving right")
            else:
                self.autocontrolbot()
        
        cv2.waitKey(1)
        
    def seekmode(self, image, M):
        if self.seek == False:
            print "entering seekmode"
        self.seek = True
        self.search = False
        self.found = False
        h, w, d = image.shape
        cx = int(M['m10']/M['m00'])
        cy = int(M['m01']/M['m00'])
        self.centrePointX = cx
        self.centrePointY = cy
        # make a circle of the centre and add it to the image
        cv2.circle(image, (cx, cy), 20, (0,0,255), -1)
          
        err = cx - w/2
        print "min total: " + str(min(self.dataranges.ranges))
        if min(self.dataranges.ranges) < 0.75 or str(min(self.dataranges.ranges)) == "nan":
            self.autocontrolbot(seekMode = True)
        else:
            self.commandChanges = 0
            self.twist.linear.x = 0.5 # set speed 
            self.twist.angular.z = -float(err) / 100 # set turn based on the amount of error from angle of current turtlebot
        self.cmd_vel_pub.publish(self.twist)
        # END CONTROL
        cv2.waitKey(1)
    
    def foundmode(self, image, M):
        if self.found == False:        
            print "entering foundmode"
            if self.MR > self.MG and self.MR > self.MY and self.MR > self.MB:
                self.color = "red"
            elif self.MG > self.MR and self.MG > self.MY and self.MG > self.MB:
                self.color = "green"
            elif self.MB > self.MR and self.MB > self.MY and self.MB > self.MG:
                self.color = "blue"
            else:
                self.color = "yellow"
            print "found color: " + self.color
        self.found = True
        self.search = False
        self.seek = False
        self.twist.linear.x = 0.0
        self.twist.angular.z = 0.5
        self.cmd_vel_pub.publish(self.twist)
        
        #self.founditer += 1
        # END CONTROL
       # if self.depth < 0.5 and M['m00'] > 100000 and self.founditer > 10:
       #     print "stopping spin at iter: " + str(self.founditer)
        self.found = False
        print "removing color " + self.color + " from mask"
        self.colors.remove(self.color)
        if len(self.colors) == 0:
            print("COMPLETED")
            sys.exit()
        print self.colors
        rospy.sleep(5)
        #self.founditer = 0
        cv2.waitKey(1)
                

rospy.init_node('follower')
follower = Follower()
rospy.spin()
