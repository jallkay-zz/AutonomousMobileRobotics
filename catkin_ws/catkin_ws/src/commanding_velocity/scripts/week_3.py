# -*- coding: utf-8 -*-
"""
Created on Mon Feb 12 15:08:04 2018

@author: user
"""

#!/usr/bin/env python

import rospy
import cv2
import numpy
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge, CvBridgeError


class image_converter:

    def __init__(self):

        cv2.namedWindow("Image window", 1)
        cv2.startWindowThread()
        self.bridge = CvBridge()
     #   self.image_sub = rospy.Subscriber("/usb_cam/image_raw",
    #                                      Image, self.callback)
        self.image_sub = rospy.Subscriber("/turtlebot_2/camera/rgb/image_raw",
                                          Image, self.callback)

    def callback(self, data):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(data, "bgr8")
        except CvBridgeError, e:
            print e

        bgr_thresh = cv2.inRange(cv_image,
                                 numpy.array((2, 10, 2)),
                                 numpy.array((2, 255, 2)))

        hsv_img = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        hsv_thresh = cv2.inRange(hsv_img,
                                 numpy.array((50, 100, 50)),
                                 numpy.array((180, 255, 255)))

        print numpy.mean(hsv_img[:, :, 0])
        print numpy.mean(hsv_img[:, :, 1])
        print numpy.mean(hsv_img[:, :, 2])

        bgr_contours, hierachy = cv2.findContours(bgr_thresh.copy(),
                                                  cv2.RETR_TREE,
                                                  cv2.CHAIN_APPROX_SIMPLE)

        hsv_contours, hierachy = cv2.findContours(hsv_thresh.copy(),
                                                  cv2.RETR_TREE,
                                                  cv2.CHAIN_APPROX_SIMPLE)
        for c in hsv_contours:
            a = cv2.contourArea(c)
            if a > 100.0:
                cv2.drawContours(cv_image, c, -1, (255, 0, 0))
        print '===='
        
        means_string = "Means: \\n%s \ \ n%s \n%s" %(numpy.mean(hsv_img[:, :, 0]), numpy.mean(hsv_img[:, :, 1]), numpy.mean(hsv_img[:, :, 2]))

        self.publisher(means_string)       
        
        cv2.imshow("Image window", hsv_thresh)
        
    def publisher(self, a):
        pub = rospy.Publisher('chatter', String, queue_size=10)
        rospy.loginfo(a)
        pub.publish(a)
        print 'Published >:D'

image_converter()
rospy.init_node('image_converter', anonymous=True)
rospy.spin()
cv2.destroyAllWindows()