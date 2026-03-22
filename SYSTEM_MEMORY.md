# SYSTEM_MEMORY.md
## 1. SYSTEM OVERVIEW
The Hospital Management Information System (HMIS) is designed to manage and streamline hospital operations, including patient records, appointments, billing, and staff management. This system is a critical component of the HMIS workflow, providing a centralized platform for hospital staff to access and manage patient data. The primary user roles that interact with this system include doctors, nurses, administrators, and receptionists.

## 2. COMPLETE DATA MODEL
The following models are used in the system:
- **User**: Represents a hospital staff member.
  - Fields:
    - `username`: The username chosen by the staff member (required).
    - `email`: The email address of the staff member (required).
    - `password`: The password for the staff member's account (required).
    - `role`: The role of the staff member (doctor, nurse, administrator, receptionist) (required).
- **Patient**: Represents a patient in the hospital.
  - Fields:
    - `name`: The patient's name (required).
    - `date_of_birth`: The patient's date of birth (required).
    - `address`: The patient's address (optional).
    - `phone_number`: The patient's phone number (optional).
- **Appointment**: Represents a scheduled appointment between a doctor and a patient.
  - Fields:
    - `date`: The date of the appointment (required).
    - `time`: The time of the appointment (required).
    - `doctor`: The doctor scheduled for the appointment (required, foreign key to User).
    - `patient`: The patient scheduled for the appointment (required, foreign key to Patient).
- **Billing**: Represents a bill for a patient's services.
  - Fields:
    - `date`: The date the bill was generated (required).
    - `amount`: The total amount of the bill (required).
    - `patient`: The patient the bill belongs to (required, foreign key to Patient).

## 3. BUSINESS RULES
The following business rules are enforced by the system:
- A user must have a unique username and email address.
- A patient's date of birth must be in the past.
- An appointment must be scheduled for a valid date and time.
- A doctor can only schedule appointments with patients who are assigned to them.
- A patient can only have one active appointment at a time.
- A bill must be generated for every appointment.
- A patient's balance must be updated after each payment.
- The system prevents duplicate appointments for the same doctor and patient on the same date and time.
- The system prevents appointments from being scheduled for dates in the past.
- The system prevents doctors from scheduling appointments with patients who are not assigned to them.
- Patients can only be assigned to one doctor at a time.

## 4. PERMISSION ARCHITECTURE
The following roles are defined in the system, along with their permissions:
- **Doctor**: Can view and edit patient records, schedule appointments, and generate bills.
- **Nurse**: Can view patient records and assist with appointments.
- **Administrator**: Can view and edit all patient records, schedule appointments, generate bills, and manage staff accounts.
- **Receptionist**: Can schedule appointments, generate bills, and assist with patient check-in.

Permissions are enforced at the model level, using Django's built-in permission system.

## 5. STATUS MACHINES
The following status machines are used in the system:
- **Appointment Status**: An appointment can be in one of the following states:
  - Scheduled: The appointment has been scheduled, but has not yet occurred.
  - In Progress: The appointment is currently in progress.
  - Completed: The appointment has been completed.
  - Cancelled: The appointment has been cancelled.
- **Patient Status**: A patient can be in one of the following states:
  - Active: The patient is currently active and receiving care.
  - Inactive: The patient is no longer active and is not receiving care.

## 6. EXISTING PATTERNS & CONVENTIONS
The following coding patterns and conventions are used in the system:
- Serializers are structured using Django Rest Framework's built-in serializer classes.
- Permissions are applied at the model level, using Django's built-in permission system.
- Validation is done using Django's built-in validation system, with custom validation rules defined as needed.
- Errors are returned using Django Rest Framework's built-in error handling system.
- Base classes and mixins are used to provide common functionality across multiple models and views.

## 7. INTEGRATION POINTS
The following integration points are used in the system:
- The system connects to other modules through Django's built-in signals and hooks system.
- The system uses shared utilities and services, such as authentication and authorization, provided by Django.
- The system uses Django's built-in support for third-party libraries and frameworks.

## 8. SAFE EXTENSION ZONES
The following areas are safe for extension:
- New models can be added to the system without affecting existing functionality.
- New endpoints can be added to the system without affecting existing functionality.
- New business rules can be added to the system without affecting existing functionality, as long as they do not conflict with existing rules.

## 9. KNOWN GAPS & INCOMPLETE LOGIC
The following areas are known to have gaps or incomplete logic:
- The system does not currently support multiple doctors for a single patient.
- The system does not currently support appointment reminders or notifications.
- The system does not currently support billing for services other than appointments.