from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from fastapi.logger import logger
from pydantic import BaseModel
from urllib import parse

import requests

_FIELD_MAPPING = {
    # Encounter Details
    "EncounterDate_Month": "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Month",
    "EncounterDate_Day": "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Day",
    "EncounterDate_Year": "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Year",
    "TreatingProvider": "ctl00$phFolderContent$ucSOAPNote$lstProvider",
    "Office": "ctl00$phFolderContent$ucSOAPNote$lstOffice",
    "EncounterType": "ctl00$phFolderContent$ucSOAPNote$lstEncounterType",
    # --- Subjective Fields ---
    "ChiefComplaint": "ctl00$phFolderContent$ucSOAPNote$S_ChiefComplaint",
    "HOPI": "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Original",
    "OnsetDate_Month": "ctl00$phFolderContent$ucSOAPNote$OnsetDate$Month",
    "OnsetDate_Day": "ctl00$phFolderContent$ucSOAPNote$OnsetDate$Day",
    "OnsetDate_Year": "ctl00$phFolderContent$ucSOAPNote$OnsetDate$Year",
    "MedicalHistory": "ctl00$phFolderContent$ucSOAPNote$S_MedicalHistory",
    "SurgicalHistory": "ctl00$phFolderContent$ucSOAPNote$S_SurgicalHistory",
    "FamilyHistory": "ctl00$phFolderContent$ucSOAPNote$S_FamilyHistory",
    "SocialHistory": "ctl00$phFolderContent$ucSOAPNote$S_SocialHistory",
    "Allergies": "ctl00$phFolderContent$ucSOAPNote$S_Allergies",
    "CurrentMedications": "ctl00$phFolderContent$ucSOAPNote$S_Medications",
    # Review of Systems (ROS)
    "ROS_Constitutional": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Constitutional",
    "ROS_Head": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Head",
    "ROS_Neck": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Neck",
    "ROS_Eyes": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Eyes",
    "ROS_Ears": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Ears",
    "ROS_Nose": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Nose",
    "ROS_Mouth": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Mouth",
    "ROS_Throat": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Throat",
    "ROS_Cardiovascular": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Cardiovascular",
    "ROS_Respiratory": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Respiratory",
    "ROS_Gastrointestinal": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Gastrointestinal",
    "ROS_Genitourinary": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Genitourinary",
    "ROS_Musculoskeletal": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Musculoskeletal",
    "ROS_Integumentary": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Skin_Breast",
    "ROS_Neurological": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Neurological",
    "ROS_Psychiatric": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Psychiatric",
    "ROS_Endocrine": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Endocrine",
    "ROS_Hematologic": "ctl00$phFolderContent$ucSOAPNote$S_ROS_Lymphatic",
    "ROS_Allergic": "ctl00$phFolderContent$ucSOAPNote$S_ROS_AllergicImmunologic",
    # --- Objective Fields ---
    "Objective": "ctl00$phFolderContent$ucSOAPNote$O_Objective",
    # Physical Exam (PE)
    "PE_General": "ctl00$phFolderContent$ucSOAPNote$O_PE_General",
    "PE_ENMT": "ctl00$phFolderContent$ucSOAPNote$O_PE_HeadEyeEarNoseThroat",
    "PE_Neck": "ctl00$phFolderContent$ucSOAPNote$O_PE_Neck",
    "PE_Respiratory": "ctl00$phFolderContent$ucSOAPNote$O_PE_Respiratory",
    "PE_Cardiovascular": "ctl00$phFolderContent$ucSOAPNote$O_PE_Cardiovascular",
    "PE_Lungs": "ctl00$phFolderContent$ucSOAPNote$O_PE_Lung",
    "PE_Chest": "ctl00$phFolderContent$ucSOAPNote$O_PE_Breast",
    "PE_Heart": "ctl00$phFolderContent$ucSOAPNote$O_PE_Heart",
    "PE_Abdomen": "ctl00$phFolderContent$ucSOAPNote$O_PE_Adomen",
    "PE_Genitourinary": "ctl00$phFolderContent$ucSOAPNote$O_PE_Genitourinary",
    "PE_Lymphatic": "ctl00$phFolderContent$ucSOAPNote$O_PE_Lymphatic",
    "PE_Musculoskeletal": "ctl00$phFolderContent$ucSOAPNote$O_PE_Musculoskeletal",
    "PE_Skin": "ctl00$phFolderContent$ucSOAPNote$O_PE_Skin",
    "PE_Extremities": "ctl00$phFolderContent$ucSOAPNote$O_PE_Extremities",
    "PE_Neurological": "ctl00$phFolderContent$ucSOAPNote$O_PE_Neurological",
    # Test Results
    "TestResults_ECG": "ctl00$phFolderContent$ucSOAPNote$O_TR_ECG",
    "TestResults_Imaging": "ctl00$phFolderContent$ucSOAPNote$O_TR_Imaging",
    "TestResults_Lab": "ctl00$phFolderContent$ucSOAPNote$O_TR_Laboratory",
    # --- Assessment Fields ---
    "AssessmentNotes_ICD10": "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$A_A_10_0",
    "AssessmentNotes_ICD9": "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$A_A_09_0",
    # --- Plan Fields ---
    "PlanNotes": "ctl00$phFolderContent$ucSOAPNote$P_Plans",
    "PatientInstructions": "ctl00$phFolderContent$ucSOAPNote$P_PatientInstructions",
    "Procedures": "ctl00$phFolderContent$ucSOAPNote$P_Procedures",
    "AdministeredMedication": "ctl00$phFolderContent$ucSOAPNote$AdminMedication",
}

DEMO_PAYLOAD = {
    "__EVENTTARGET": "",
    "__EVENTARGUMENT": "",
    "__LASTFOCUS": "",
    "__VIEWSTATE": "PLACEHOLDER",
    "__VIEWSTATEGENERATOR": "226FEE4A",
    "__SCROLLPOSITIONX": "0",
    "__SCROLLPOSITIONY": "248.8000030517578",
    "__VIEWSTATEENCRYPTED": "",
    "__RequestVerificationToken": "WTJPZdo4yn6btUNBKT8bWc6BvFlWLBbQBIf5tSQXArrfeL5HSFN6EPUX89yAnid8ghn1Rzpb-Swyqd9Owg_TXCUAUu-WM--NGbp4mScPpCxGwTdSjSkkHtXzOYSuk02rSlJDQMSXLK9I9XWbDA7dEQS-6vU1",
    "PageAction": "",
    "PatientID": "",
    "ID": "",
    "ctl00$phFolderContent$PatientChartsScripts$hdnMissingPatientID": "",
    "ctl00$phFolderContent$myPatientHeader$PatientImageFileName": "",
    "ctl00$phFolderContent$myPatientHeader$PatientDOB": "01/01/1900",
    "ctl00$phFolderContent$myPatientHeader$PatientAge": "125 yrs. 5 mos. old",
    "ctl00$phFolderContent$myPatientHeader$PatientGender": "M",
    "ctl00$phFolderContent$myPatientHeader$PatientWeight": "",
    "ctl00$phFolderContent$myPatientHeader$hdnDate1": "",
    "ctl00$phFolderContent$myPatientHeader$hdnDate2": "",
    "ctl00$phFolderContent$myPatientHeader$AddEducationalResourcePopup$hdnPatientName": "4TH, OF JULY",
    "activeelement": "",
    "aeselpos": "",
    "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Month": "6",
    "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Day": "5",
    "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Year": "2025",
    "ctl00$phFolderContent$ucSOAPNote$lstProvider": "198417",
    "ctl00$phFolderContent$ucSOAPNote$lstTreatingProviderRole": "1",
    "ctl00$phFolderContent$ucSOAPNote$lstOffice": "166396",
    "ctl00$phFolderContent$ucSOAPNote$lstEncounterType": "1",
    "ctl00$phFolderContent$ucSOAPNote$ddlInfoSource": "",
    "ctl00$phFolderContent$ucSOAPNote$lstSpecialty": "",
    "ctl00$phFolderContent$ucSOAPNote$lstSOAPGuideline": "0",
    "ctl00$phFolderContent$ucSOAPNote$LOS": "Vijai Daniel",
    "ctl00$phFolderContent$ucSOAPNote$ReferringProviderID": "0",
    "ctl00$phFolderContent$ucSOAPNote$ReferringProvider": " ",
    "ctl00$phFolderContent$ucSOAPNote$btnTriggerSave": ".",
    "ctl00$phFolderContent$ucSOAPNote$ddlSoapLayout": "347185",
    "ctl00$phFolderContent$ucSOAPNote$ReasonForVisit": "",
    "ctl00$phFolderContent$ucSOAPNote$NurseNote": "",
    "ctl00$phFolderContent$ucSOAPNote$chkPrint_CPT": "on",
    "ctl00$phFolderContent$ucSOAPNote$S_ChiefComplaint": "Testing chief complaint",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Original": "Testing History of Presnet Illness",
    "ctl00$phFolderContent$ucSOAPNote$OnsetDate$Month": "",
    "ctl00$phFolderContent$ucSOAPNote$OnsetDate$Day": "",
    "ctl00$phFolderContent$ucSOAPNote$OnsetDate$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$ddlAdvancedDirectiveType": "100000",
    "ctl00$phFolderContent$ucSOAPNote$DateReviewed$Month": "",
    "ctl00$phFolderContent$ucSOAPNote$DateReviewed$Day": "",
    "ctl00$phFolderContent$ucSOAPNote$DateReviewed$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$S_MedicalHistory": "",
    "ctl00$phFolderContent$ucSOAPNote$S_SurgicalHistory": "",
    "ctl00$phFolderContent$ucSOAPNote$S_FamilyHistory": "",
    "ctl00$phFolderContent$ucSOAPNote$S_SocialHistory": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlSmokingStatus": "0",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlSmokingFrequency": "0",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlSmokingStartDateType": "3",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingStartDate$Month": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingStartDate$Day": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingStartDate$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlSmokingEndDateType": "3",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingEndDate$Month": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingEndDate$Day": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingEndDate$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlTobaccoSNOMEDCode": "0",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlTobaccoFrequency": "0",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlTobaccoStartDateType": "3",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$TobaccoStartDate$Month": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$TobaccoStartDate$Day": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$TobaccoStartDate$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$ddlTobaccoEndDateType": "3",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$TobaccoEndDate$Month": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$TobaccoEndDate$Day": "01",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$TobaccoEndDate$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$LastTobaccoUseReviewDate$Month": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$LastTobaccoUseReviewDate$Day": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$LastTobaccoUseReviewDate$Year": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$SmokingComments": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$hdnSmokingStartDate": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$hdnSmokingEndDate": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$hdnTobaccoStartDate": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$hdnTobaccoEndDate": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$hdnLastTobaccoUseReviewDate": "",
    "ctl00$phFolderContent$ucSOAPNote$PatientSmoking$hdnStatusID": "340",
    "ctl00$phFolderContent$ucSOAPNote$hdnddlAllergiesType": "0",
    "ctl00$phFolderContent$ucSOAPNote$ddlAllergiesType": "0",
    "ctl00$phFolderContent$ucSOAPNote$S_AllergiesInputSelection": "2",
    "ctl00$phFolderContent$ucSOAPNote$S_Allergies": "",
    "ctl00$phFolderContent$ucSOAPNote$S_MedicationsInputSelection": "2",
    "ctl00$phFolderContent$ucSOAPNote$S_Medications": "ROI test",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Constitutional": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Head": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Neck": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Eyes": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Ears": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Nose": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Mouth": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Throat": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Cardiovascular": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Respiratory": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Gastrointestinal": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Genitourinary": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Musculoskeletal": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Skin_Breast": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Neurological": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Psychiatric": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Endocrine": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Lymphatic": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_AllergicImmunologic": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom1": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Height2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Weight2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BMI2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BloodPressure_Systolic2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BloodPressure_Diastolic2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Temperature2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Pulse2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_RespRate2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_HeadCircumference2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Waist2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Glucose2txt": "",
    "ctl00$phFolderContent$ucSOAPNote$O_Objective": "Objective Notes",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_General": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_HeadEyeEarNoseThroat": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Neck": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Respiratory": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Cardiovascular": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Lung": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Breast": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Heart": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Adomen": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Genitourinary": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Lymphatic": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Musculoskeletal": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Skin": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Extremities": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Neurological": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom1": "",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_ECG": "",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Imaging": "",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Laboratory": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$ICDType": "rdICD_10",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_09_12": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_09_12": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$A_A_09_0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_12": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_12": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$A_A_10_0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnGuideline": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnGuidelineLength": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnGuidelineText": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_0": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_0": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Display": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Display": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnInsuranceID": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnInsuranceName": "",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnInsuranceSwitchDate": "10/01/2015",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_1": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_1": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_1": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_1": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_1": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_1": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_2": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_2": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_2": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_2": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_2": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_2": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_3": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_3": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_3": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_3": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_3": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_3": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_4": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_4": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_4": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_4": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_4": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_4": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_5": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_5": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_5": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_5": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_5": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_5": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_6": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_6": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_6": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_6": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_6": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_6": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_7": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_7": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_7": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_7": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_7": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_7": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_8": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_8": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_8": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_8": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_8": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_8": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_9": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_9": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_9": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_9": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_9": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_9": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_10": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_10": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_10": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_10": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_10": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_10": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_11": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_11": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_11": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_11": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_11": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_11": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_ID_12": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_Type_12": "1",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_09_AID_12": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_ID_12": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_Type_12": "3",
    "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$hdnICD_10_AID_12": "0",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTNdc": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId0": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId1": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId2": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId3": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId4": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId5": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId6": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId7": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId8": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId9": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId10": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTCode11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDescription11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTPOS11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierA11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierB11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierC11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTModifierD11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTDiagPointer11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTFee11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$EncounterCPTUnit11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$NationalDrugCodeId11": "",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$hdnJsonString": "[]",
    "ctl00$phFolderContent$ucSOAPNote$ucCPT$hdnLoadJsonString": "",
    "ctl00$phFolderContent$ucSOAPNote$P_Procedures": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnVISIDs": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnVISPublicationIDs": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnVISPublicationDateHTML": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnMultipleVISID": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnMultipleVISDate": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnSendToRegistry": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnInventoryID": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnImmunizationRequestID": "",
    "ctl00$phFolderContent$ucSOAPNote$ucImmunization$ucAddImmunization$hdnRequiredDemographics": "",
    "ctl00$phFolderContent$ucSOAPNote$S_Immunization": "",
    "ctl00$phFolderContent$ucSOAPNote$ucAdminMed$hdnLoginUserName": "vdaniel2025",
    "ctl00$phFolderContent$ucSOAPNote$ucAdminMed$hdnCompanyID": "315658",
    "ctl00$phFolderContent$ucSOAPNote$ucAdminMed$ucAddAdministeredMedication$hdnDrugID": "",
    "ctl00$phFolderContent$ucSOAPNote$ucAdminMed$ucAddAdministeredMedication$hdnDrugName": "",
    "ctl00$phFolderContent$ucSOAPNote$ucAdminMed$ucAddAdministeredMedication$hdnDrugTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$ucAdminMed$ucAddAdministeredMedication$hdnRxNormDrugId": "",
    "ctl00$phFolderContent$ucSOAPNote$AdminMedication": "",
    "ctl00$phFolderContent$ucSOAPNote$P_Plans": "",
    "ctl00$phFolderContent$ucSOAPNote$P_PatientInstructions": "",
    "Task": "Update",
    "OrderIDs": "",
    "CopyFromEncounterID": "",
    "ctl00$phFolderContent$ucSOAPNote$hasMultipleTaxIds": "N",
    "ctl00$phFolderContent$ucSOAPNote$hdnScrollPos": "0",
    "ctl00$phFolderContent$ucSOAPNote$EncounterID": "325206320",
    "ctl00$phFolderContent$ucSOAPNote$OfficeID": "",
    "ctl00$phFolderContent$ucSOAPNote$EncounterType": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ChiefComplaint_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Original_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Expanded_Flag": "",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Location_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Quality_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Severity_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Duration_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Timing_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HistoryOfPresentIllness_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_ModifyingFactors_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_HOPI_AssociatedSigns_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_OnsetDate_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_History_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_MedicalHistory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_SurgicalHistory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_FamilyHistory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_SocialHistory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_GynecologicalHistory_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Constitutional_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Head_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Neck_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Eyes_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Ears_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Nose_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Mouth_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Throat_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Cardiovascular_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Respiratory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Gastrointestinal_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Genitourinary_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Musculoskeletal_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Skin_Breast_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Neurological_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Psychiatric_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Lymphatic_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Endocrine_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_AllergicImmunologic_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_Allergies_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_Immunization_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_Medications_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_UseValidationControls": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_UnitOfMeasurement_Selected_Flag": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BloodPressure_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_DisplayDate_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BloodPressureSide_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BloodPressurePosition_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_BMI_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Pulse_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Temperature_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Weight_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_WeightOunces_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Height_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_RespRate_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Waist_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_HeadCircumference_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Glucose_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_EDD_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_LMP_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_GrowthChart_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_Objective_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_General_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_HeadEyeEarNoseThroat_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Head_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Eye_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Ear_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Nose_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Mouth_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Throat_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Neck_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Lung_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Breast_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Heart_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Adomen_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Genitourinary_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Respiratory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Musculoskeletal_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Cardiovascular_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Neurological_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Skin_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Lymphatic_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Extremities_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_CognitiveStatus_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_FunctionalStatus_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_ECG_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Imaging_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Laboratory_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Custom1_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_TR_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$A_SNOMEDCodes_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$ProcedureCodes_Flag": "",
    "ctl00$phFolderContent$ucSOAPNote$A_CancerCase_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Procedures_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$P_ProceduresNotDone_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Labs_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Medications_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_MedicationsNotPrescribed_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Plans_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$P_Goals_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_PatientInstructions_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$P_PatientComments_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$AdvancedDirective_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom1_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom3_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom4_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom1_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom3_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom4_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom1_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom3_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom4_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom1_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom3_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom4_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$A_SocialPsychologicalBehavioral_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$A_Custom1_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$A_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$A_Health_Concerns_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom1_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom3_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom4_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom1_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom2_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom3_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$S_Custom4_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$P_AdministeredMedication_Flag": "Y",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom1_Label": "Review of Systems",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom2_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom3_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$S_ROS_Custom4_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom1_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom2_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom3_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_Custom4_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom1_Label": "Physical Exam",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom2_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom3_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$O_PE_Custom4_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnO_VS_DateRecorded": "",
    "ctl00$phFolderContent$ucSOAPNote$A_Custom1_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$A_Custom2_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom1_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom2_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom3_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$P_Custom4_Label": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnUpdateDemographics": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSmokingStatus": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSmokingFrequency": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnUnitOfMeasurementID": "2",
    "ctl00$phFolderContent$ucSOAPNote$hdnCurrentlyNoMedications": "False",
    "ctl00$phFolderContent$ucSOAPNote$hdnCurrentlyNoAllergies": "False",
    "ctl00$phFolderContent$ucSOAPNote$hdnAllergyListReviewed": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnHealthMaintenanceDesc": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnHealthMaintenanceDueDate": "",
    "ctl00$phFolderContent$ucSOAPNote$AutoSave": "1200",
    "ctl00$phFolderContent$ucSOAPNote$NewCropActivationDate": "",
    "ctl00$phFolderContent$ucSOAPNote$P_NQFRecommendations": "",
    "ctl00$phFolderContent$ucSOAPNote$VitalSignAlerts": "False",
    "ctl00$phFolderContent$ucSOAPNote$hdnImmunID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigAction": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigDosageActionTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigDosageNumberTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigDosageFormTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigDosageRouteTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigDosageFrequencyTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigDosageProblemTypeID": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnSigInformation": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnjsonCPTAlert": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnExpandROS": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnExpandPE": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnExpandTR": "",
    "ctl00$phFolderContent$ucSOAPNote$hdnHasClicked": "6",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_O2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$O_VS_SpO2_Flag": "N",
    "ctl00$phFolderContent$ucSOAPNote$chkPrint_NQF": "N",
    "ctl00$phFolderContent$ucSOAPNote$inputEhrLogin": "",
    "OrderType": "",
    "img": "",
    "ctl00$ucVIM$hdnPatientInfo": '{"identifiers":{"ehrPatientId":"57089800","mrn":"57089800"},"demographics":{"firstName":"OF JULY","lastName":"4TH","middleName":"","dateOfBirth":null,"gender":"male"},"address":{"address1":"","address2":"","city":"","state":"","zipCode":"","fullAddress":" , , , "},"insurance":{"ehrInsurance":"","groupId":"","payerId":"","memberId":""},"contact_info":{"homePhoneNumber":"","mobilePhoneNumber":"","email":""},"pcp":{"ehrProviderId":"0","npi":"","demographics":{"firstName":"","lastName":"","middleName":""}}}',
    "ctl00$ucVIM$hdnEncounterInfo": '{"identifiers":{"ehrEncounterId":"325206320"},"provider":{"ehrProviderId":"198417","npi":"1043473986","demographics":{"firstName":"VIJAI","lastName":"DANIEL, MD","middleName":""},"facility":{"facilityEhrId":"166396","name":"VIJAI J. DANIEL, M.D.","address":{"address1":"1660 E HERNDON AVE SUITE 101","address2":"","city":"FRESNO","state":"CA","zipCode":"93720-3346","fullAddress":"1660 E HERNDON AVE SUITE 101 , FRESNO, CA, 93720-3346"},"contact_info":{"mobilePhoneNumber":"559-431-9753","homePhoneNumber":"559-431-9753","faxNumber":"559-431-3478","email":""}},"specialty":[{"description":"Internal Medicine","taxonomies":["207RP1001X"]}],"providerDegree":"MD"},"assessment":{"diagnosisCodes":[]},"basicInformation":{"status":"UNLOCKED","encounterDateOfService":"2025-06-05"}}',
    "ctl00$ucVIM$hdnReferralInfo": "",
}


def _extract_form_fields(html_content: str, form_id_or_name: str) -> Dict[str, str]:
    """
    Extracts all input, select, and textarea fields from a specified form in HTML.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    form = soup.find("form", {"id": form_id_or_name})
    if not form:
        form = soup.find("form", {"name": form_id_or_name})
    if not form:
        logger.debug(f"Warning: Form with id/name '{form_id_or_name}' not found.")
        return {}

    data = {}
    for input_tag in form.find_all("input"):
        name = input_tag.get("name")
        value = input_tag.get("value", "")
        if name:
            if input_tag.get("type") == "radio":
                if input_tag.has_attr("checked"):
                    data[name] = value
            elif input_tag.get("type") == "checkbox":
                if input_tag.has_attr("checked"):
                    data[name] = value if value else "on"
            else:
                data[name] = value

    for select_tag in form.find_all("select"):
        name = select_tag.get("name")
        if name:
            selected_option = select_tag.find("option", selected=True)
            if selected_option and selected_option.has_attr("value"):
                data[name] = selected_option["value"]
            elif select_tag.find("option"):
                first_option = select_tag.find("option")
                if first_option and first_option.has_attr("value"):
                    data[name] = first_option["value"]
                else:
                    data[name] = ""
            else:
                data[name] = ""

    for textarea_tag in form.find_all("textarea"):
        name = textarea_tag.get("name")
        if name:
            data[name] = textarea_tag.string or ""

    return data


def _extract_form_fields_with_token(
    html_content: str, form_id_or_name: str
) -> Tuple[Dict[str, str], Optional[str]]:
    soup = BeautifulSoup(html_content, "html.parser")
    form_data = _extract_form_fields(html_content, form_id_or_name)

    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    anti_forgery_token = None
    if token_input and token_input.has_attr("value"):
        anti_forgery_token = token_input["value"]
        form_data["__RequestVerificationToken"] = anti_forgery_token
    elif "__RequestVerificationToken" in form_data:
        anti_forgery_token = form_data["__RequestVerificationToken"]
    else:
        logger.debug(
            "Warning: __RequestVerificationToken input field not found in HTML."
        )
    hdn_json_input = soup.find("input", {"id": re.compile("hdnJsonString$")})
    if hdn_json_input and hdn_json_input.get("name"):
        form_data["hdn_json_cpt_string_name"] = hdn_json_input["name"]
        logger.debug(
            f"    Found hdnJsonString field name: {form_data["hdn_json_cpt_string_name"]}"
        )

    return form_data, anti_forgery_token


def _extract_form_data_for_date_change(
    soup: BeautifulSoup, target_date_str: str
) -> Dict[str, str]:
    form_data = {}
    critical_asp_fields = [
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "__RequestVerificationToken",
    ]
    for name in critical_asp_fields:
        inp = soup.find("input", {"name": name})
        if inp and inp.has_attr("value"):
            form_data[name] = inp["value"]
        else:
            logger.debug(
                f"Warning: Critical ASP.NET field '{name}' not found or has no value for date change."
            )
            form_data[name] = ""

    default_fields = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "ctl00$phFolderContent$ucAppointmentScripts$hdnType": "",
        "ctl00$phFolderContent$Appointments$hdnType": "",
        "ctl00$phFolderContent$Appointments$lstOffice": "166396",
        "ctl00$phFolderContent$Appointments$lstProvider": "198417",
        "ctl00$phFolderContent$Appointments$lstTimeInterval": "15",
        "NewAppointmentDay": "27",
        "NewAppointmentMonth": "5",
        "NewAppointmentYear": "2025",
        "SelectedOffice": "166396",
        "SelectedProvider": "198417",
        "PageAction": "",
        "PatientID": "",
        "Time": "",
        "DT": "",
        "ID": "",
        "Day": "",
        "Month": "",
        "Year": "",
        "ctl00$phFolderContent$Appointments$hdnSwitchDate": "",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime1": "08:00",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime1": "17:00",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2": "08:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2": "16:15",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime3": "08:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime3": "16:15",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime4": "08:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime4": "16:15",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime5": "08:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime5": "16:15",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime6": "08:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime6": "16:15",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime7": "08:00",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime7": "17:00",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_1": "00:00",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_1": "00:00",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_2": "13:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_2": "16:30",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_3": "13:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_3": "16:30",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_4": "13:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_4": "16:30",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_5": "13:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_5": "16:30",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_6": "13:30",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_6": "16:30",
        "ctl00$phFolderContent$Appointments$AppointmentStartTime2_7": "00:00",
        "ctl00$phFolderContent$Appointments$AppointmentStopTime2_7": "00:00",
        "ctl00$phFolderContent$Appointments$OperatingWeekDays": "NYYYYYN",
        "ctl00$phFolderContent$Appointments$Use2ndSession": "NNNNNNN",
        "ctl00$phFolderContent$Appointments$AppointmentTimeInterval": "15",
        "ctl00$phFolderContent$Appointments$hdnScrollY": "0",
        "ctl00$phFolderContent$Appointments$CellLineCount": "",
        "ctl00$phFolderContent$Appointments$ProviderCount": "",
        "ctl00$phFolderContent$Appointments$ResourceStart": "",
        "ctl00$phFolderContent$Appointments$ResourceStop": "",
        "ctl00$phFolderContent$Appointments$CellWidth": "",
        "ctl00$phFolderContent$Appointments$ProviderID": "198417",
        "ctl00$phFolderContent$Appointments$HeightMinuteRatio": "",
        "ctl00$phFolderContent$Appointments$CellColumnCount": "",
        "ctl00$phFolderContent$Appointments$ShowAppReminder": "",
        "ctl00$phFolderContent$Appointments$goToDay": "",
        "img": "",
        "ctl00$ucVIM$hdnPatientInfo": "",
        "ctl00$ucVIM$hdnEncounterInfo": "",
        "ctl00$ucVIM$hdnReferralInfo": "",
        "__SCROLLPOSITIONX": "0",
        "ctl00$phFolderContent$Appointments$hdnGoToDate": target_date_str,
        "ctl00$phFolderContent$Appointments$btnGotoDate": " Go To Date ",
    }

    for name, default_val in default_fields.items():
        if name in form_data:
            continue

        inp = soup.find("input", {"name": name, "type": "hidden"})
        if inp and inp.has_attr("value"):
            form_data[name] = inp["value"]
        else:
            select_tag = soup.find("select", {"name": name})
            if select_tag:
                selected_opt = select_tag.find("option", selected=True)
                form_data[name] = (
                    selected_opt["value"]
                    if selected_opt
                    else (
                        select_tag.find("option")["value"]
                        if select_tag.find("option")
                        else default_val
                    )
                )
            else:
                form_data[name] = default_val

    try:
        dt_obj = datetime.strptime(target_date_str, "%m/%d/%Y")
        form_data["ctl00$phFolderContent$Appointments$GoToDate$Month"] = str(
            dt_obj.month
        )
        form_data["ctl00$phFolderContent$Appointments$GoToDate$Day"] = str(dt_obj.day)
        form_data["ctl00$phFolderContent$Appointments$GoToDate$Year"] = str(dt_obj.year)
    except ValueError:
        logger.debug(
            f"Error: Invalid target_date_str format '{target_date_str}'. Expected MM/DD/YYYY."
        )
        raise ValueError("Invalid target_date_str format. Expected MM/DD/YYYY.")

    # logger.debug(
    #     f"Extracted form data for date change: { {k: v[:10] + '...' if isinstance(v, str) and len(v) > 20 else v for k,v in form_data.items()} }"
    # )
    return form_data


def _parse_appointments_from_html(
    html_content: str, calendar_date_for_appointments: str
) -> List[Dict[str, Any]]:
    """Parses appointment details from the HTML calendar table."""
    soup = BeautifulSoup(html_content, "html.parser")
    appointments: List[Dict[str, Any]] = []

    page_displayed_date_str = "Unknown"
    calendar_title_div = soup.find("div", id="divCalendarTitle")
    if calendar_title_div:
        date_td = calendar_title_div.find("td", class_="frameheader", align="center")
        if date_td:
            page_displayed_date_str = date_td.text.strip()

    appointment_table = soup.select_one("div#divDaily table.tblAppts")
    if not appointment_table:
        logger.debug("Appointment table (div#divDaily table.tblAppts) not found.")
        return appointments

    current_hour_display_str = ""

    thead = appointment_table.find("thead")
    if not thead:
        logger.debug("Appointment table header (thead) not found.")
        return appointments

    for row_idx, row in enumerate(thead.find_next_siblings("tr")):
        cols = row.find_all("td", recursive=False)

        if len(cols) < 15:
            continue

        hour_cell_text = cols[0].text.strip()
        if hour_cell_text:
            current_hour_display_str = hour_cell_text

        minute_cell_html = str(cols[1])
        minute_cell_text_content = cols[1].text.strip()

        minutes_match = re.search(r":(\d+)", minute_cell_text_content)
        minutes_str = "00"
        if minutes_match:
            minutes_str = minutes_match.group(1).zfill(2)

        am_pm_suffix = "AM"
        if "<small>pm</small>" in minute_cell_html.lower():
            am_pm_suffix = "PM"

        if not current_hour_display_str:
            full_time_str = "Unknown Time"
        else:
            full_time_str = f"{current_hour_display_str.zfill(2)}:{minutes_str} {am_pm_suffix}".strip()

        patient_name_anchor = cols[2].find("a")
        patient_name_text = cols[2].text.strip().replace(" ", "").strip()

        if not (patient_name_anchor and patient_name_anchor.text.strip()):
            if (
                "BLOCK" in patient_name_text.upper()
                or "BLOCK" in cols[8].text.strip().upper()
            ):
                patient_name = patient_name_text if patient_name_text else "BLOCK"
            else:
                continue
        else:
            patient_name = patient_name_anchor.text.strip()

        def get_cell_text(col_idx):
            return cols[col_idx].text.strip().replace(" ", "").strip()

        patient_id = get_cell_text(3)
        visit_length = get_cell_text(4)
        dob = get_cell_text(5)
        home_phone = get_cell_text(6)
        provider_name = get_cell_text(7)
        reason_for_visit = get_cell_text(8)
        status = get_cell_text(9)

        appointments.append(
            {
                "date": calendar_date_for_appointments,
                "page_displayed_date": page_displayed_date_str,
                "time": full_time_str,
                "patient_name": patient_name,
                "patient_id": patient_id,
                "visit_length_minutes": visit_length,
                "dob": dob,
                "home_phone": home_phone,
                "provider_name": provider_name,
                "reason_for_visit": reason_for_visit,
                "status": status,
            }
        )

    return appointments


def _extract_anti_forgery_token(html_content: str) -> Optional[str]:
    soup = BeautifulSoup(html_content, "html.parser")
    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if token_input and token_input.has_attr("value"):
        return token_input["value"]
    logger.debug(
        "Warning: __RequestVerificationToken input field not found in PatientChart.aspx HTML."
    )
    return None


def _parse_patient_phi_from_html(html_content: str) -> Dict[str, Any]:
    """Parses patient PHI from the patient chart summary HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    phi_data: Dict[str, Any] = {}

    def get_span_text(span_id: str, default_val: Any = None) -> Optional[str]:
        span = soup.find("span", id=span_id)
        if span:
            return span.text.strip()
        return default_val

    phi_data["patient_id"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblPatientID"
    )
    phi_data["dob_age"] = get_span_text("ctl00_phFolderContent_myPatientHeader_lblDOB")
    phi_data["preferred_language"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblLanguage"
    )

    phi_data["last_name"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblLastName"
    )
    phi_data["sex"] = get_span_text("ctl00_phFolderContent_myPatientHeader_lblGender")
    phi_data["race"] = get_span_text("ctl00_phFolderContent_myPatientHeader_lblRace")

    phi_data["first_name"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblFirstName"
    )
    phi_data["phone"] = get_span_text("ctl00_phFolderContent_myPatientHeader_lblPhone")
    phi_data["ethnicity"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblEthnicity"
    )

    phi_data["middle_name"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblMiddleName"
    )
    phi_data["insurance_name"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblInsuranceName"
    )
    phi_data["smoke_status"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblSmoke"
    )

    phi_data["primary_care_provider"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblPrimaryCareProvider"
    )
    phi_data["insurance_type"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblInsuranceType"
    )
    phi_data["alternate_patient_id"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblAlternatePatientID"
    )  # Might be hidden by style
    phi_data["patient_ally_id"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblPatientAllyID"
    )

    phi_data["favorite_pharmacy"] = get_span_text(
        "ctl00_phFolderContent_myPatientHeader_lblFavoritePharmacy"
    )

    phi_data["__RequestVerificationToken"] = _extract_anti_forgery_token(html_content)

    if phi_data["dob_age"]:
        parts = phi_data["dob_age"].split(" - Age: ")
        phi_data["dob"] = parts[0].strip() if parts else None
        phi_data["age_details"] = parts[1].strip() if len(parts) > 1 else None
    else:
        phi_data["dob"] = None
        phi_data["age_details"] = None

    return phi_data


def _extract_encounter_ids_from_script(html_content: str) -> List[str]:
    """
    Extracts encounter IDs from the JavaScript block in PatientChart_ProgressNotes.aspx.
    Specifically targets: var strIDs = 'id1;id2;id3';
    """
    soup = BeautifulSoup(html_content, "html.parser")
    scripts = soup.find_all("script", type="text/javascript")
    all_encounter_ids = []

    for script in scripts:
        if script.string:
            match = re.search(r"var\s+strIDs\s*=\s*'([^']+)';", script.string)
            if match:
                ids_string = match.group(1)
                if ids_string:
                    all_encounter_ids.extend(ids_string.split(";"))
                break

    return [eid for eid in all_encounter_ids if eid]


def perform_pre_submission_check(
    session: requests.Session, headers, patient_id, auth_token
):
    """
    Performs the asynchronous validation check with the correct payload format and auth token.
    """
    logger.debug("-> Performing pre-submission validation check...")
    api_url = f"https://pm.officeally.com/emr/CommonUserControls/Ajax/WebAPI/Api.aspx?method=POST&url=v1/patients/patientInformation/patientID/{patient_id}"

    # The HAR file shows the 'ProcedureCodes' array is populated with empty placeholders.
    # While it's empty in this specific interaction, we'll build it to match the structure.
    # If CPT codes were entered, this array would be populated.
    procedure_codes = []
    # In a real scenario, you would loop through the CPT code inputs on the page
    # to build this list. For this replication, we'll use the empty structure from the HAR.
    for _ in range(38):  # The HAR file showed 38 empty objects.
        procedure_codes.append(
            {
                "PatientID": int(patient_id),
                "DateOfService": "6/6/2025",
                "DateOfBirth": "01/01/1900",
            }
        )

    # This is the inner 'data' object, which gets stringified.
    inner_data = {
        "DiagnosisCodes": "[]",  # Empty array as a string
        "ProcedureCodes": json.dumps(procedure_codes),  # Array of objects, stringified
    }

    # This is the main JSON object that forms the request body.
    # The 'data' field itself contains a JSON string.
    api_payload_dict = {
        "url": f"v1/patients/patientInformation/patientID/{patient_id}",
        "urlparam": [],
        "data": json.dumps(inner_data),
        "method": "POST",
        "contenttype": None,
        "headers": [],
        "type": 1,
        "usetoken": True,
    }

    # The final data sent is the URL-encoded version of this dictionary.
    final_api_data = parse.urlencode(api_payload_dict)

    # Set up headers specific to this API call.
    api_headers = headers.copy()
    api_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    api_headers["X-Requested-With"] = "XMLHttpRequest"
    api_headers["X-OA-AUTH-TOKEN"] = auth_token  # Use the extracted token here

    try:
        response = session.post(api_url, headers=api_headers, data=final_api_data)
        if response.status_code == 200:
            logger.debug("-> Pre-submission check successful (Status 200).")
            return True
        else:
            logger.debug(
                f"[ERROR] Pre-submission check failed with status code {response.status_code}."
            )
            # logger.debug(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.debug(f"[ERROR] Network error during pre-submission check: {e}")
        return False


def create_progress_note_incremental(html_content):
    """
    Automates creating a progress note by using a known-good payload as a template
    and incrementally updating it with dynamic values found in the HTML source.
    """
    logger.debug(
        "--- Office Ally Progress Note Automation (Incremental Update Method) ---"
    )
    soup = BeautifulSoup(html_content, "html.parser")
    form = soup.find("form", {"id": "aspnetForm"})
    if not form:
        raise FileNotFoundError(
            "Could not find the <form> with id='aspnetForm' in the HTML."
        )

    # Create a working copy of our template
    payload = DEMO_PAYLOAD.copy()

    # Incrementally update payload with values from the HTML
    for key in DEMO_PAYLOAD:
        element = form.find(["input", "select", "textarea"], {"name": key})
        if not element:
            continue  # Keep the template value if element not found

        value = None
        if element.name == "input":
            value = element.get("value", "")
        elif element.name == "select":
            selected_option = element.find("option", selected=True)
            value = selected_option.get("value", "") if selected_option else None
        elif element.name == "textarea":
            value = element.get_text()

        # ONLY update the payload if the HTML provides a non-empty value
        if value:
            payload[key] = value

    # Sanity check for critical dynamic fields
    if "PLACEHOLDER" in payload["__VIEWSTATE"]:
        logger.debug(
            "\n[ERROR] Critical field '__VIEWSTATE' was not found in the HTML and could not be updated."
        )
        return

    logger.debug("-> Dynamic values updated successfully.")
    return payload


class SOAPNotes(BaseModel):
    # Subjective
    ChiefComplaint: Optional[str] = None
    HOPI: Optional[str] = None
    OnsetDate_Month: Optional[str] = None
    OnsetDate_Day: Optional[str] = None
    OnsetDate_Year: Optional[str] = None
    MedicalHistory: Optional[str] = None
    SurgicalHistory: Optional[str] = None
    FamilyHistory: Optional[str] = None
    SocialHistory: Optional[str] = None
    Allergies: Optional[str] = None
    CurrentMedications: Optional[str] = None
    ROS_Constitutional: Optional[str] = None
    ROS_Head: Optional[str] = None
    ROS_Neck: Optional[str] = None
    ROS_Eyes: Optional[str] = None
    ROS_Ears: Optional[str] = None
    ROS_Nose: Optional[str] = None
    ROS_Mouth: Optional[str] = None
    ROS_Throat: Optional[str] = None
    ROS_Cardiovascular: Optional[str] = None
    ROS_Respiratory: Optional[str] = None
    ROS_Gastrointestinal: Optional[str] = None
    ROS_Genitourinary: Optional[str] = None
    ROS_Musculoskeletal: Optional[str] = None
    ROS_Integumentary: Optional[str] = None
    ROS_Neurological: Optional[str] = None
    ROS_Psychiatric: Optional[str] = None
    ROS_Endocrine: Optional[str] = None
    ROS_Hematologic: Optional[str] = None
    ROS_Allergic: Optional[str] = None

    # Objective
    Objective: Optional[str] = None
    PE_General: Optional[str] = None
    PE_ENMT: Optional[str] = None
    PE_Neck: Optional[str] = None
    PE_Respiratory: Optional[str] = None
    PE_Cardiovascular: Optional[str] = None
    PE_Lungs: Optional[str] = None
    PE_Chest: Optional[str] = None
    PE_Heart: Optional[str] = None
    PE_Abdomen: Optional[str] = None
    PE_Genitourinary: Optional[str] = None
    PE_Lymphatic: Optional[str] = None
    PE_Musculoskeletal: Optional[str] = None
    PE_Skin: Optional[str] = None
    PE_Extremities: Optional[str] = None
    PE_Neurological: Optional[str] = None
    TestResults_ECG: Optional[str] = None
    TestResults_Imaging: Optional[str] = None
    TestResults_Lab: Optional[str] = None

    # Assessment
    AssessmentNotes_ICD10: Optional[str] = None
    AssessmentNotes_ICD9: Optional[str] = None

    # Plan
    PlanNotes: Optional[str] = None
    PatientInstructions: Optional[str] = None
    Procedures: Optional[str] = None
    AdministeredMedication: Optional[str] = None


class EncounterDetails(BaseModel):
    EncounterDate_Month: str
    EncounterDate_Day: str
    EncounterDate_Year: str
    TreatingProvider: Optional[str] = "198417"
    Office: Optional[str] = "166396"
    EncounterType: Optional[str] = "1"


class CreateProgressNotesRequest(BaseModel):
    patient_id: str
    soap_notes: SOAPNotes
    encounter_details: EncounterDetails


class AllyLoginCredentials(BaseModel):
    username: str
    password: str
    validate_creds: Optional[bool] = True
