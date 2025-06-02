# **Office Ally Unofficial API**

This project integrates with **Office Ally's Practice Mate (PM) and Electronic Health Record (EHR)** systems to manage user sessions, retrieve patient information, handle appointments, and create/update clinical progress notes. It aims to provide programmatic access to key functionalities within the Office Ally platform.

---

## **Endpoints**

### **Authentication & Session Management**

- **POST** `/add-credentials` – Authenticate Office Ally credentials and establish a session.
  - _Input_: Office Ally username and password.
  - _Output_: Success message

### **Appointments**

- **GET** `/fetch-appointments` – Get Appointments List for a specific date, office, and provider.
  - _Input_: Date (MM/DD/YYYY), Office ID, Provider ID.
  - _Output_: List of appointments with details.

### **Patient Clinical Data**

- **GET** `/fetch-phi` – Retrieve Patient Health Information (PHI) / Demographics.
  - _Input_: Patient ID.
  - _Output_: Structured patient demographic and summary data.
- **GET** `/fetch-progressnotes` – Fetch a list of Progress Note Encounter IDs for a patient.
  - _Input_: Patient ID.
  - _Output_: List of Encounter IDs.
- **POST** `/create-progressnote` – Create a new Progress Note.
  - _Input_: Patient ID, encounter details (date, provider, office, type), SOAP note content (Chief Complaint, HOPI, Objective, Assessment, Plan, etc.).
  - _Output_: New Encounter ID and status message.

---

## **Info**

This unofficial API client for **Office Ally** is built by **[Integuru.ai](https://integuru.ai/)**. We specialize in creating robust integrations and automating interactions with various platforms. We take custom requests for new platforms or additional features for existing ones, and also offer hosting and advanced authentication management services.

If you have requests or want to collaborate, please reach out at **richard@taiki.online**.

Here's a **[complete list](https://github.com/Integuru-AI/APIs-by-Integuru)** of unofficial APIs built by Integuru.ai.
This repository is part of our broader integrations package: **[GitHub Repo](https://github.com/Integuru-AI/Integrations)**.
