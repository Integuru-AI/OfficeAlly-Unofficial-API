import re
from bs4 import BeautifulSoup
import requests
from submodule_integrations.models.integration import Integration
from submodule_integrations.office_ally.office_ally_integrations_utility import (
    _FIELD_MAPPING,
    DiagnosisCode,
    ProcedureCode,
    _extract_encounter_ids_from_script,
    _extract_form_data_for_date_change,
    _extract_form_fields_with_token,
    _parse_appointments_from_html,
    _parse_patient_phi_from_html,
    create_progress_note_incremental,
    perform_pre_submission_check,
)
from submodule_integrations.utils.errors import (
    IntegrationError,
    IntegrationAPIError,
    IntegrationAuthError,
)
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from fastapi.logger import logger


class AllyIntegration(Integration):
    def __init__(
        self,
        active_session: requests.Session,
    ):
        super().__init__("ecw")
        self.session = active_session
        self.base_url = "https://pm.officeally.com/emr"

    @classmethod
    async def create(
        cls,
        session_object: requests.Session,
        network_requester=None,
    ):
        instance = cls(
            session_object,
        )
        instance.network_requester = network_requester
        return instance

    def _setup_headers(
        self,
        content_type: str = None,
        referer: str = None,
        is_ajax: bool = False,
        antiforge_token: str = None,
    ) -> Dict[str, str]:
        _headers = {
            "Accept-Language": "en-US,en;q=0.9",
        }
        if content_type:
            _headers["Content-Type"] = content_type
        if referer:
            _headers["Referer"] = referer
        if is_ajax:
            _headers["X-Requested-With"] = "XMLHttpRequest"
            _headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        else:
            _headers["Accept"] = (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
            )
        if antiforge_token and is_ajax:
            logger.debug(f"Adding antiforge token: {antiforge_token}")
            _headers["x-oa-auth-token"] = antiforge_token
        return _headers

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        full_url = urljoin(self.base_url + "/", url)
        logger.debug(f"Making {method} request to: {full_url}")
        logger.debug(
            f"Request kwargs (partial): headers_set={kwargs.get('headers') is not None}, data_present={kwargs.get('data') is not None}"
        )
        if "data" in kwargs and isinstance(kwargs["data"], dict):
            logger.debug(
                f"Request data (first 200 chars if long): {str(kwargs['data'])[:200]}"
            )

        try:
            response = self.session.request(method, full_url, timeout=60, **kwargs)
            logger.debug(f"Response status: {response.status_code}")
            # try:
            #     logger.debug(f"Response text (first 300 chars): {response.text[:300]}")
            # except Exception:
            #     logger.debug("Could not log response text (binary or other issue).")

            if response.history:
                for r_hist in response.history:
                    if "Login.aspx" in r_hist.headers.get(
                        "Location", ""
                    ) or "auth0bridge" in r_hist.headers.get("Location", ""):
                        logger.debug(
                            f"Redirected to login during request to {full_url}. Effective URL: {response.url}"
                        )
                        raise IntegrationAuthError(
                            "Session expired or invalid, redirected to login.",
                            status_code=r_hist.status_code,
                            error_code="SESSION_EXPIRED_REDIRECT",
                        )
            if response.status_code == 302 and (
                "Login.aspx" in response.headers.get("Location", "")
                or "auth0bridge" in response.headers.get("Location", "")
            ):
                logger.debug(
                    f"Redirected to login during request to {full_url} (no history, direct 302). Effective URL: {response.url}"
                )
                raise IntegrationAuthError(
                    "Session expired or invalid, redirected to login.",
                    status_code=response.status_code,
                    error_code="SESSION_EXPIRED_DIRECT_REDIRECT",
                )

            return response
        except requests.exceptions.Timeout:
            logger.debug(f"Request timed out: {method} {full_url}")
            raise IntegrationAPIError(
                self.integration_name, "Request timed out", 504, "TIMEOUT"
            )
        except requests.exceptions.ConnectionError as e:
            logger.debug(f"Connection error: {method} {full_url} - {e}")
            raise IntegrationAPIError(
                self.integration_name, f"Connection error: {e}", 503, "CONNECTION_ERROR"
            )
        except requests.exceptions.RequestException as e:
            logger.debug(f"Generic request exception: {method} {full_url} - {e}")
            status_code = e.response.status_code if e.response is not None else 500
            raise IntegrationAPIError(
                self.integration_name,
                f"Request failed: {e}",
                status_code,
                "REQUEST_EXCEPTION",
            )

    def _handle_response(self, response: requests.Response) -> Any:
        response_text = response.text
        status = response.status_code
        parsed_data = None

        try:
            logger.debug(f"Response text (first 300 chars): {response_text[:300]}")
        except Exception:
            logger.debug("Could not log response text (binary or other issue).")

        # Check if we were redirected to login, even if status is 200
        if status == 200 and (
            "Login.aspx" in response.url or "auth0bridge" in response.url
        ):
            logger.debug(
                f"Response status 200 but URL indicates login page: {response.url}"
            )
            raise IntegrationAuthError(
                "Operation resulted in redirection to login page, possibly due to session expiry.",
                status_code=status,
                error_code="AUTH_REDIRECT_LOGIN_ON_200",
            )

        try:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type or response_text.startswith("{"):
                # logger.debug("Got a JSON response")
                parsed_data = response.json()
            elif "html" in content_type:
                parsed_data = {
                    "type": "html",
                    "content_preview": response_text[:200],
                }
            else:
                logger.debug(
                    f"Uncommon Content-Type: {content_type}. Returning raw text."
                )
                return response_text
        except json.JSONDecodeError as e:
            logger.debug(
                f"JSON response parsing failed: {e}. Raw text: {response_text[:500]}"
            )
            parsed_data = {
                "error": {
                    "message": "JSON parsing error",
                    "raw_preview": response_text[:500],
                }
            }
        except Exception as e:
            logger.debug(
                f"Response parsing failed: {e}. Raw text: {response_text[:500]}"
            )
            parsed_data = {
                "error": {
                    "message": f"Generic parsing error: {type(e).__name__}",
                    "raw_preview": response_text[:500],
                }
            }

        if 200 <= status < 300:
            if (
                isinstance(parsed_data, dict)
                and "dt" in parsed_data
                and isinstance(parsed_data["dt"], str)
            ):
                try:
                    # logger.debug("We're here!")
                    nested_json = json.loads(parsed_data["dt"])
                    parsed_data["decoded_dt"] = nested_json
                    parsed_data.pop("dt")
                    if (
                        isinstance(nested_json, dict)
                        and nested_json.get("Message") == "Fail"
                    ):
                        logger.debug(
                            f"API call successful (HTTP 200) but internal API indicated failure: {nested_json}"
                        )
                        raise IntegrationAPIError(
                            self.integration_name,
                            nested_json.get("Error", "API indicated failure"),
                            status,
                            "API_INTERNAL_FAILURE",
                        )
                except json.JSONDecodeError:
                    logger.debug(
                        f"Failed to parse nested JSON in 'dt' field: {parsed_data['dt'][:100]}"
                    )
            # logger.debug(f"Parsed Data: {parsed_data}")
            return parsed_data

        error_message = "Unknown error"
        error_code_str = str(status)

        if (
            isinstance(parsed_data, dict)
            and "error" in parsed_data
            and isinstance(parsed_data["error"], dict)
        ):
            error_message = parsed_data["error"].get("message", error_message)
            error_code_str = parsed_data["error"].get("code", error_code_str)
        elif isinstance(parsed_data, dict) and "Message" in parsed_data:
            error_message = parsed_data.get("Message", error_message)
            error_code_str = parsed_data.get("Status", error_code_str)

        logger.debug(
            f"Error response: Status {status}, Message: {error_message}, Code: {error_code_str}, Parsed: {str(parsed_data)[:200]}"
        )

        if status == 401 or status == 403:
            raise IntegrationAuthError(error_message, status, error_code_str)
        elif 400 <= status < 500:
            raise IntegrationAPIError(
                self.integration_name, error_message, status, error_code_str
            )
        elif status >= 500:
            raise IntegrationAPIError(
                self.integration_name,
                f"Downstream server error: {error_message}",
                status,
                error_code_str,
            )
        else:
            raise IntegrationAPIError(
                self.integration_name,
                f"Unhandled status {status}: {error_message}",
                status,
                error_code_str,
            )

    async def get_appointments_for_date(
        self,
        target_date_str: str,
        office_id: str = "166396",
        provider_id: str = "198417",
    ) -> List[Dict[str, Any]]:
        """
        Fetches appointments for a specific date.
        """
        appointments_url_path = "Appointments/ViewAppointments.aspx?Tab=A"

        logger.debug(f"Fetching initial appointments page: {appointments_url_path}")
        initial_headers = self._setup_headers()
        response_get = self._make_request(
            "GET", appointments_url_path, headers=initial_headers, allow_redirects=True
        )

        initial_html_content = response_get.text
        current_url_after_get = response_get.url

        logger.debug(
            f"Successfully fetched initial appointment page. Effective URL: {current_url_after_get}"
        )

        soup_for_form = BeautifulSoup(initial_html_content, "html.parser")
        form_payload = _extract_form_data_for_date_change(
            soup_for_form, target_date_str
        )

        form_payload["ctl00$phFolderContent$Appointments$lstOffice"] = office_id
        form_payload["ctl00$phFolderContent$Appointments$lstProvider"] = provider_id
        form_payload["SelectedOffice"] = office_id
        form_payload["SelectedProvider"] = provider_id

        logger.debug(f"Posting to change date to: {target_date_str}")

        post_headers = self._setup_headers(
            content_type="application/x-www-form-urlencoded",
            referer=current_url_after_get,
        )

        response_post = self._make_request(
            "POST",
            appointments_url_path,
            headers=post_headers,
            data=form_payload,
            allow_redirects=True,
        )

        html_for_target_date = response_post.text

        logger.debug(
            f"Successfully posted for date change. Effective URL after POST: {response_post.url}"
        )

        appointments = _parse_appointments_from_html(
            html_for_target_date, target_date_str
        )
        logger.debug(f"Found {len(appointments)} appointments for {target_date_str}.")
        return appointments

    async def get_patient_phi(self, patient_id: str) -> Dict[str, Any]:
        if not patient_id:
            logger.debug(
                "Error: Patient ID (PID) must be provided for get_patient_phi."
            )
            raise ValueError("Patient ID (PID) must be provided.")

        phi_url_path = "PatientCharts/PatientChart_Summary.aspx"
        params = {"Tab": "C", "PageAction": "Summary", "PID": patient_id}

        headers = self._setup_headers()

        response = self._make_request(
            "GET", f"{phi_url_path}?{urlencode(params)}", headers=headers
        )

        html_content = response.text

        if (
            "patient could not be found" in html_content.lower()
            or "error has occurred" in html_content.lower()
        ):
            logger.debug(f"Patient PID {patient_id} not found or error on page.")
            raise IntegrationAPIError(
                self.integration_name,
                f"Patient {patient_id} not found or error on page.",
                404,
                "PATIENT_NOT_FOUND",
            )

        parsed_phi = _parse_patient_phi_from_html(html_content)
        if not parsed_phi.get("patient_id"):
            logger.debug(
                f"Failed to parse significant PHI data for patient {patient_id} from HTML."
            )
        return parsed_phi

    def _utility_fetch_single_progress_note_json(
        self,
        patient_id: str,
        encounter_id: str,
        age_years: int,
        age_months: int,
        antiforge_token: Optional[str],
        age_days: int = 0,
    ) -> Optional[Dict[str, Any]]:
        logger.debug(f"Fetching single progress note JSON for EID: {encounter_id}")
        if not antiforge_token:
            logger.debug(
                f"    CRITICAL: No AntiForgeryToken provided for API call to get note EID {encounter_id}. Aborting API call."
            )
            raise IntegrationAPIError(
                "Missing AntiForgeryToken, cannot fetch progress note details.",
                error_code="MISSING_AJAX_TOKEN_FOR_NOTE",
            )
            # return None  # Or raise error

        api_path_for_payload_and_query = (
            f"v1/encounters/{encounter_id}/patients/{patient_id}/viewprogressnote"
            f"?ageYears={age_years}&ageMonths={age_months}&ageDays={age_days}"
        )
        api_url_path = f"CommonUserControls/Ajax/WebAPI/Api.aspx?method=GET&url={api_path_for_payload_and_query}"

        post_payload_json_obj = {
            "url": api_path_for_payload_and_query,
            "urlparam": [],
            "data": [],
            "method": "GET",
            "contenttype": None,
            "headers": [],
            "type": 6,
            "usetoken": True,
        }

        headers = self._setup_headers(
            content_type="application/x-www-form-urlencoded; charset=UTF-8",
            is_ajax=True,
            antiforge_token=antiforge_token,
        )

        try:
            response = self._make_request(
                "POST",
                api_url_path,
                data=json.dumps(post_payload_json_obj),
                headers=headers,
            )
            parsed_response = self._handle_response(response)

            if isinstance(parsed_response, dict):
                return parsed_response
            else:
                logger.debug(
                    f"Unexpected structure in API response for note EID {encounter_id}: {str(parsed_response)[:300]}"
                )
                return None
        except IntegrationError as e:
            logger.debug(
                f"Error fetching single progress note EID {encounter_id}: {e.message}"
            )
            raise

    async def get_progress_notes_content(
        self,
        patient_id: str,
        encounter_id: Optional[str] = None,
        fetch_all_if_no_encounter_id: bool = False,
        max_notes_to_fetch_if_all: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Fetches progress note(s) JSON content.
        """
        logger.debug(
            f"get_progress_notes_content called for PID: {patient_id}, EID: {encounter_id}"
        )

        try:
            patient_phi = await self.get_patient_phi(patient_id)
            antiforge_token = patient_phi.get("__RequestVerificationToken")
            if not antiforge_token:
                logger.debug(
                    f"CRITICAL: Could not get __RequestVerificationToken from patient PHI for PID {patient_id}."
                )
                raise IntegrationAuthError(
                    "Missing AntiForgeryToken, cannot fetch progress notes via API.",
                    error_code="MISSING_AJAX_TOKEN",
                )

            age_details_str = patient_phi.get("age_details", "")
            age_years, age_months, age_days = 0, 0, 0  # Defaults
            if age_details_str:
                match_years = re.search(r"(\d+)\s*yrs", age_details_str)
                match_months = re.search(r"(\d+)\s*mos", age_details_str)
                if match_years:
                    age_years = int(match_years.group(1))
                if match_months:
                    age_months = int(match_months.group(1))
            logger.debug(f"Using age: {age_years}y {age_months}m for API call.")

        except IntegrationError as e:
            logger.debug(
                f"Failed to get patient PHI/token for PID {patient_id}: {e.message}"
            )
            raise

        progress_notes_data: List[Dict[str, Any]] = []

        if encounter_id:
            logger.debug(f"Fetching specific progress note for EID: {encounter_id}")
            note_json = self._utility_fetch_single_progress_note_json(
                patient_id,
                encounter_id,
                age_years,
                age_months,
                antiforge_token,
                age_days=0,
            )
            if note_json:
                progress_notes_data.append(note_json)
        else:
            logger.debug(f"Fetching list of encounter IDs for PID: {patient_id}")
            progress_notes_list_url_path = (
                "PatientCharts/PatientChart_ProgressNotes.aspx"
            )
            params = {
                "PageAction": "ProgressNotes,PatientCharts_ProgressNotes_Add",
                "Tab": "C",
                "PID": patient_id,
                "Scope": "",
                "Date1": "",
                "Date2": "",
            }
            headers_html = self._setup_headers(
                referer=f"{self.base_url}/PatientCharts/PatientChart_Summary.aspx?PID={patient_id}"
            )

            response = self._make_request(
                "GET",
                f"{progress_notes_list_url_path}?{urlencode(params)}",
                headers=headers_html,
            )
            html_content = response.text

            encounter_ids_to_fetch = _extract_encounter_ids_from_script(html_content)
            if not encounter_ids_to_fetch:
                logger.debug(f"No encounter IDs found for PID {patient_id}.")
                return []

            logger.debug(
                f"Found {len(encounter_ids_to_fetch)} encounter IDs: {encounter_ids_to_fetch[:5]}..."
            )

            ids_to_process = (
                encounter_ids_to_fetch[:max_notes_to_fetch_if_all]
                if not fetch_all_if_no_encounter_id
                else encounter_ids_to_fetch
            )
            logger.debug(f"Processing {len(ids_to_process)} encounter IDs.")

            for eid in ids_to_process:
                note_json = self._utility_fetch_single_progress_note_json(
                    patient_id,
                    eid,
                    age_years,
                    age_months,
                    antiforge_token,
                    age_days=0,
                )
                if note_json:
                    progress_notes_data.append(note_json)

        return progress_notes_data

    def _translate_user_data(self, user_note_data: dict) -> dict:
        """
        Translates simplified keys in user_note_data to their full ASP.NET names.
        """
        translated_data = {}
        for key, value in user_note_data.items():
            if key in _FIELD_MAPPING:
                translated_data[_FIELD_MAPPING[key]] = value
            else:
                translated_data[key] = value
        return translated_data

    async def create_progress_note(
        self,
        patient_id: str,
        soap_notes: Dict[str, str],
        encounter_details: Dict[str, str],
        diagnosis_codes: Optional[List[DiagnosisCode]] = None,
        procedure_codes: Optional[List[ProcedureCode]] = None,
        soap_layout_id: str = "347185",
    ) -> Tuple[Optional[str], str]:
        logger.debug(f"Attempting to create progress note for PID: {patient_id}")
        if not patient_id:
            return None, "Patient ID (PID) must be provided."
        if not soap_notes:
            return None, "SOAP note content must be provided."
        if not all(
            k in encounter_details
            for k in [
                "EncounterDate_Month",
                "EncounterDate_Day",
                "EncounterDate_Year",
                "TreatingProvider",
                "Office",
                "EncounterType",
            ]
        ):
            return (
                None,
                "Essential encounter details (Date, Provider, Office, Type) are missing.",
            )

        base_url_page_path = "PatientCharts/PatientChart_EditNote.aspx"
        query_params = {
            "PageAction": "AddNote",
            "SoapLayoutID": soap_layout_id,
            "Tab": "C",
            "PID": patient_id,
            "Scope": "",
            "Date1": "",
            "Date2": "",
        }
        edit_note_url_path = f"{base_url_page_path}?{urlencode(query_params)}"

        logger.debug(f"Fetching 'AddNote' page: {edit_note_url_path}")
        headers_get = self._setup_headers(
            referer=f"{self.base_url}/PatientCharts/PatientChart_Summary.aspx?PID={patient_id}"
        )
        response_get = self._make_request(
            "GET", edit_note_url_path, headers=headers_get, allow_redirects=True
        )
        initial_html_content = response_get.text
        current_url_after_get = response_get.url

        # form_data, _ = _extract_form_fields_with_token(
        #     initial_html_content, "aspnetForm"
        # )
        form_data = create_progress_note_incremental(initial_html_content)
        if not form_data.get("__VIEWSTATE"):
            logger.debug("CRITICAL: __VIEWSTATE not found on AddNote page.")
            return None, "Could not extract __VIEWSTATE from AddNote page."

        for key, value in self._translate_user_data(soap_notes).items():
            form_data[key] = value
        for key, value in self._translate_user_data(encounter_details).items():
            form_data[key] = value

        if diagnosis_codes:
            for i, diag in enumerate(diagnosis_codes):
                if i >= 12:
                    break  # OfficeAlly form only has 12 slots
                code_key = (
                    f"ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dc_10_{i+1}"
                )
                desc_key = (
                    f"ctl00$phFolderContent$ucSOAPNote$ucDiagnosisCodes$dd_10_{i+1}"
                )
                form_data[code_key] = diag.code
                form_data[desc_key] = diag.description

        if procedure_codes:
            cpt_json_list = []
            num_cpt_codes = len(procedure_codes)

            for i in range(12):
                base_name = f"ctl00$phFolderContent$ucSOAPNote$ucCPT$SoapNoteCPT$"

                if i < num_cpt_codes:
                    cpt = procedure_codes[i]
                    form_data[f"{base_name}EncounterCPTCode{i}"] = cpt.code
                    form_data[f"{base_name}EncounterCPTDescription{i}"] = (
                        cpt.description
                    )
                    form_data[f"{base_name}EncounterCPTPOS{i}"] = cpt.pos
                    form_data[f"{base_name}EncounterCPTModifierA{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierB{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierC{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierD{i}"] = ""
                    form_data[f"{base_name}EncounterCPTDiagPointer{i}"] = ""
                    form_data[f"{base_name}EncounterCPTFee{i}"] = cpt.fee
                    form_data[f"{base_name}EncounterCPTUnit{i}"] = cpt.units
                    form_data[f"{base_name}EncounterCPTNdc"] = ""
                    form_data[f"{base_name}NationalDrugCodeId{i}"] = ""

                    cpt_object = {
                        "EncounterCPTLineNumber": str(i + 1),
                        "EncounterCPTCode": cpt.code,
                        "EncounterCPTDescription": cpt.description,
                        "EncounterCPTPOS": cpt.pos,
                        "EncounterCPTModifierA": "",
                        "EncounterCPTModifierB": "",
                        "EncounterCPTModifierC": "",
                        "EncounterCPTModifierD": "",
                        "EncounterCPTDiagPointer": "",
                        "EncounterCPTFee": cpt.fee,
                        "EncounterCPTUnit": cpt.units,
                        "EncounterCPTNdc": "",
                        "NationalDrugCodeId": 0,
                    }
                    cpt_json_list.append(cpt_object)
                else:
                    form_data[f"{base_name}EncounterCPTCode{i}"] = ""
                    form_data[f"{base_name}EncounterCPTDescription{i}"] = ""
                    form_data[f"{base_name}EncounterCPTPOS{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierA{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierB{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierC{i}"] = ""
                    form_data[f"{base_name}EncounterCPTModifierD{i}"] = ""
                    form_data[f"{base_name}EncounterCPTDiagPointer{i}"] = ""
                    form_data[f"{base_name}EncounterCPTFee{i}"] = ""
                    form_data[f"{base_name}EncounterCPTUnit{i}"] = ""
                    form_data[f"{base_name}EncounterCPTNdc{i}"] = ""
                    form_data[f"{base_name}NationalDrugCodeId{i}"] = ""

            form_data["ctl00$phFolderContent$ucSOAPNote$chkPrint_CPT"] = "no"

        form_data["ctl00$phFolderContent$ucSOAPNote$ucCPT$hdnJsonString"] = json.dumps(
            cpt_json_list
        )
        form_data["ctl00$phFolderContent$ucSOAPNote$ucCPT$hdnLoadJsonString"] = ""
        form_data["ctl00$phFolderContent$ucSOAPNote$hdnHasClicked"] = 1

        logger.debug(
            f"Posting new note data to Office Ally form action (derived from GET): {urlparse(current_url_after_get).path}"
        )

        post_target_url_path = f"https://pm.officeally.com/emr/PatientCharts/PatientChart_EditNote.aspx?PageAction=AddNote&SoapLayoutID=347185&Tab=C&PID={patient_id}&Scope=&Date1=&Date2="

        headers_post = self._setup_headers(
            content_type="application/x-www-form-urlencoded",
            referer=post_target_url_path,
        )

        try:
            patient_phi = await self.get_patient_phi(patient_id)
            patient_dob = patient_phi.get("dob")

            if perform_pre_submission_check(
                self.session,
                headers_post,
                patient_id,
                form_data["__RequestVerificationToken"],
                diagnosis_codes,
                procedure_codes,
                patient_dob,
            ):
                logger.debug(
                    "Pre-submission check passed. Proceeding with API call to populate note."
                )
                response_post = self._make_request(
                    "POST",
                    post_target_url_path,
                    data=form_data,
                    headers=headers_post,
                    allow_redirects=False,
                )

                logger.debug(f"Create Note POST status: {response_post.status_code}")
                logger.debug(f"Create Note Response Headers: {response_post.headers}")

                if response_post.status_code == 302:
                    location_header = response_post.headers.get("Location")
                    if not location_header:
                        return (
                            None,
                            "Note creation POST resulted in 302 but no Location header.",
                        )

                    logger.debug(f"Redirected after create to: {location_header}")
                    parsed_location = urlparse(location_header)
                    query_params_redirect = parse_qs(parsed_location.query)
                    new_eid = query_params_redirect.get("EID", [None])[0]

                    if new_eid:
                        return (
                            new_eid,
                            f"Successfully created note. New Encounter ID: {new_eid}",
                        )
                    else:
                        return (
                            form_data.get(
                                "ctl00$phFolderContent$ucSOAPNote$EncounterID"
                            ),
                            f"Note creation POST redirected, but EID not found in Location: {location_header}",
                        )

                logger.debug(
                    f"Note creation POST did not redirect as expected. Status: {response_post.status_code}"
                )
                return (
                    form_data.get("ctl00$phFolderContent$ucSOAPNote$EncounterID"),
                    f"Note creation POST returned status {response_post.status_code}. Check response for errors.",
                )
            else:
                logger.debug(
                    "Pre-submission check failed. Cannot populate progress notes"
                )
                raise IntegrationAPIError(
                    "office_ally",
                    "There has been an error in creating progress notes. The server got an unexpected response from the pre-validation request. As such, the progress note is created but remains unpopulated",
                    status_code=502,
                    error_code="VALIDATION_FAILED",
                )

        except IntegrationAuthError:
            raise
        except IntegrationAPIError as e:
            return None, f"API Error during note creation POST: {e.message}"
        except Exception as e:
            logger.debug(
                f"Unexpected error during note creation POST: {e}", exc_info=True
            )
            return None, f"Unexpected error during POST: {e}"
