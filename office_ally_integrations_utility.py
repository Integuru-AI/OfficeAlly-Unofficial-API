from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from fastapi.logger import logger
from pydantic import BaseModel

_FIELD_MAPPING = {
    "ChiefComplaint": "ctl00$phFolderContent$ucSOAPNote$S_ChiefComplaint",
    "HOPI": "ctl00$phFolderContent$ucSOAPNote$S_HOPI_Original",
    "Objective": "ctl00$phFolderContent$ucSOAPNote$O_Objective",
    "AssessmentNotes": "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$A_A_10_0",  # For ICD-10 Assessment
    "PlanNotes": "ctl00$phFolderContent$ucSOAPNote$P_Plans",
    "PatientInstructions": "ctl00$phFolderContent$ucSOAPNote$P_PatientInstructions",
    "Procedures": "ctl00$phFolderContent$ucSOAPNote$P_Procedures",
    # Common header fields that are often required
    "EncounterDate_Month": "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Month",
    "EncounterDate_Day": "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Day",
    "EncounterDate_Year": "ctl00$phFolderContent$ucSOAPNote$EncounterDate$Year",
    "TreatingProvider": "ctl00$phFolderContent$ucSOAPNote$lstProvider",
    "Office": "ctl00$phFolderContent$ucSOAPNote$lstOffice",
    "EncounterType": "ctl00$phFolderContent$ucSOAPNote$lstEncounterType",
    "CPTCodes_JSON": "ctl00$phFolderContent$ucSOAPNote$ucCPT$hdnJsonString",
    "DiagnosisCode_1_ICD10": "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_1",
    "DiagnosisDescription_1_ICD10": "ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_1",
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
        print(f"Warning: Form with id/name '{form_id_or_name}' not found.")
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
        print(
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
        print("Appointment table (div#divDaily table.tblAppts) not found.")
        return appointments

    current_hour_display_str = ""

    thead = appointment_table.find("thead")
    if not thead:
        print("Appointment table header (thead) not found.")
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


class SOAPNotes(BaseModel):
    ChiefComplaint: Optional[str] = None
    HOPI: Optional[str] = None
    Objective: Optional[str] = None
    AssessmentNotes: Optional[str] = None
    PlanNotes: Optional[str] = None
    PatientInstructions: Optional[str] = None
    Procedures: Optional[str] = None


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
