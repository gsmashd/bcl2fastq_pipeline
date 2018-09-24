"""
Misc. functions
"""

import configparser
import shutil
import smtplib
from email.mime.text import MIMEText
import xml.etree.ElementTree as ET
from reportlab.lib import colors, utils
from reportlab.platypus import BaseDocTemplate, Table, Preformatted, Paragraph, Spacer, Image, Frame, NextPageTemplate, PageTemplate, TableStyle, PageBreak, ListFlowable, ListItem
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape
from time import strftime
from reportlab.pdfgen import canvas
import csv
import sys
import glob
import pathlib
import os
import os.path
import syslog
import stat
import codecs
import requests
import json


def getSampleID(sampleTuple, project, lane, sampleName) :
    if(sampleTuple is None) :
        return " "
    for item in sampleTuple :
        if(sampleName == item[1] and
            lane == item[2] and
            project == item[3]) :
            return item[0]
    return " "


def getFCmetrics(root) :
    barcode = root[0][0] #Sample "all", barcode "all"
    message = "Lane\t# Clusters (% pass)\t% Bases >=Q30\tAve. base qual.\n"
    for lane in barcode.findall("Lane") :
        message += "Lane %s" % lane.get("number")
        clusterCount = 0
        clusterCountPass = 0
        baseYield = [0,0]
        baseYieldQ30 = [0,0]
        QualSum = [0,0]
        rlens=[0,0]
        for tile in lane :
            clusterCount += int(tile[0][0].text)
            clusterCountPass += int(tile[1][0].text)
            #Yield
            baseYield[0] += int(tile[1][1][0].text)
            if(len(tile[1]) == 3) :
                baseYield[1] += int(tile[1][2][0].text)
            #YieldQ30
            baseYieldQ30[0] += int(tile[1][1][1].text)
            if(len(tile[1]) == 3) :
                baseYieldQ30[1] += int(tile[1][2][1].text)
            #QualSum
            QualSum[0] += int(tile[1][1][2].text)
            if(len(tile[1]) == 3) :
                QualSum[1] += int(tile[1][2][2].text)
        #Number of clusters (%passing filter)
        try:
            message += "\t%i (%5.2f%%)" % (clusterCount,100*clusterCountPass/clusterCount)
        except:
            message += "\t%i (NA)" % (clusterCount)
        #%bases above Q30
        if(baseYield[1] > 0) :
            try:
                message += "\t%5.2f%%/%5.2f%%" % (100*(baseYieldQ30[0]/baseYield[0]),
                    100*(baseYieldQ30[1]/baseYield[1]))
            except:
                message += "\tNA/NA"
        else :
            try:
                message += "\t%5.2f%%" % (100*(baseYieldQ30[0]/baseYield[0]))
            except:
                message += "\tNA"
        #Average base quality
        if(baseYield[1] > 0) :
            try:
                message += "\t%4.1f/%4.1f\n" % (QualSum[0]/float(baseYield[0]),
                    QualSum[1]/float(baseYield[1]))
            except:
                message += "\tNA/NA\n"
        else :
            try:
                message += "\t%4.1f\n" % (QualSum[0]/float(baseYield[0]))
            except:
                message += "\tNA\n"

    return message

def parseConversionStats(config) :
    """
    Parse ConversionStats.xml, producing:
     1) A PDF file for each project
     2) A message that will be included in the email message
    """
    lanes = config.get("Options", "lanes")
    if lanes != "":
        lanes = "_lanes{}".format(lanes)

    try :
        tree = ET.parse("%s/%s%s/Stats/ConversionStats.xml" % (config.get("Paths","outputDir"),config.get("Options","runID"), lanes))
        root = tree.getroot()[0] #We only ever have a single flow cell
    except :
        return None
    metrics = None
    #Per-project PDF files
    for project in root.findall("Project") :
        if(project.get("name") == "default") :
            continue
        if(project.get("name") == "all") :
            metrics = getFCmetrics(project)
    return metrics

def enoughFreeSpace(config) :
    """
    Ensure that outputDir has at least minSpace gigs
    """
    (tot,used,free) = shutil.disk_usage(config.get("Paths","outputDir"))
    free /= 1024*1024*1024
    if(free >= float(config.get("Options","minSpace"))) :
        return True
    return False

def errorEmail(config, errTuple, msg) :
    msg = MIMEText(msg + "\nError type: %s\nError value: %s\n%s\n" % (errTuple[0], errTuple[1], errTuple[2]))
    msg['Subject'] = "[bcl2fastq_pipeline] Error"
    msg['From'] = config.get("Email","fromAddress")
    msg['To'] = config.get("Email","errorTo")

    s = smtplib.SMTP(config.get("Email","host"))
    s.send_message(msg)
    s.quit()

def finishedEmail(config, msg, runTime, transferTime) :
    lanes = config.get("Options", "lanes")
    if lanes != "":
        lanes = "_lanes{}".format(lanes)

    message = "Flow cell: %s%s\n" % (config.get("Options","runID"), lanes)
    message += "Run time: %s\n" % runTime
    message += "Data transfer: %s\n" % transferTime
    message += msg

    msg = MIMEText(message)
    msg['Subject'] = "[bcl2fastq_pipeline] %s%s processed" % (config.get("Options","runID"), lanes)
    msg['From'] = config.get("Email","fromAddress")
    msg['To'] = config.get("Email","finishedTo")

    s = smtplib.SMTP(config.get("Email","host"))
    s.send_message(msg)
    s.quit()

