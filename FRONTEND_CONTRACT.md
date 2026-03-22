# FRONTEND_CONTRACT.md
## 1. SYSTEM CAPABILITIES SUMMARY
- Admin can create, update, and delete users under any condition.
- Doctor can view, update their own profile, and assign patients if they are assigned to the doctor.
- Nurse can view, update patient records if the patient is assigned to them.
- Receptionist can schedule appointments for patients with available doctors.
- Admin can manage appointments, patients, doctors, and nurses.
- Patient can view their appointments, medical records, and assigned doctor.
- Doctor can view their assigned patients, schedule appointments, and update patient records.

## 2. DATA CONTRACTS
### User Entity
- **required fields to send:** username, password, email, role (patient, doctor, nurse, receptionist, admin)
- **returned fields:** id, username, email, role
- **exact allowed values for role:** patient, doctor, nurse, receptionist, admin
- **read-only fields:** id
- **write-once fields:** role

### Patient Entity
- **required fields to send:** name, date_of_birth, contact_number
- **returned fields:** id, name, date_of_birth, contact_number, assigned_doctor
- **exact allowed values for assigned_doctor:** doctor IDs
- **read-only fields:** id, assigned_doctor
- **write-once fields:** None

### Doctor Entity
- **required fields to send:** name, specialty
- **returned fields:** id, name, specialty
- **exact allowed values for specialty:** cardiology, neurology, oncology, etc.
- **read-only fields:** id
- **write-once fields:** None

### Appointment Entity
- **required fields to send:** date, time, patient_id, doctor_id
- **returned fields:** id, date, time, patient_id, doctor_id, status
- **exact allowed values for status:** pending, confirmed, cancelled
- **read-only fields:** id
- **write-once fields:** patient_id, doctor_id

## 3. ROLE BASED UI RULES
- **Admin:** can access all pages, perform all actions, view all records.
- **Doctor:** can view and update their own profile, view and update assigned patient records, schedule appointments.
- **Nurse:** can view and update assigned patient records.
- **Receptionist:** can schedule appointments, view patient and doctor records.
- **Patient:** can view their appointments, medical records, and assigned doctor.

## 4. STATE BASED UI RULES
- **Appointment Entity:** 
  - **pending:** can be confirmed or cancelled by receptionist or doctor.
  - **confirmed:** can be cancelled by receptionist or doctor.
  - **cancelled:** cannot be updated.
- **Patient Entity:** 
  - **active:** can be assigned to a doctor, can have appointments scheduled.
  - **inactive:** cannot be assigned to a doctor, cannot have appointments scheduled.

## 5. FORM REQUIREMENTS
- **Create User Form:** 
  - **required fields:** username, password, email, role
  - **optional fields:** None
  - **validation rules:** username must be unique, password must meet password policy
  - **after submission:** user is created, logged in if role is not admin.
- **Create Appointment Form:** 
  - **required fields:** date, time, patient_id, doctor_id
  - **optional fields:** None
  - **validation rules:** date and time must be in the future, patient and doctor must exist.
  - **after submission:** appointment is created, patient and doctor are notified.

## 6. ERROR STATES
- **Create User Error:** 
  - **username already exists:** display error message, do not create user.
  - **password does not meet policy:** display error message, do not create user.
- **Create Appointment Error:** 
  - **date and time are in the past:** display error message, do not create appointment.
  - **patient or doctor does not exist:** display error message, do not create appointment.

## 7. WORKFLOW SEQUENCES
- **Receptionist schedules appointment:** 
  1. Selects patient from existing records.
  2. Selects available doctor.
  3. Picks date and time.
  4. System checks for conflicts.
  5. Appointment created in pending state.
  6. Receptionist notified of success.
- **Doctor assigns patient:** 
  1. Doctor views list of available patients.
  2. Doctor selects patient to assign.
  3. System checks if patient is already assigned.
  4. Patient is assigned to doctor.
  5. Doctor notified of success.

## 8. CONDITIONAL UI BEHAVIOR
- **Appointment form:** 
  - **doctor_id field:** only shows if patient has a doctor assigned.
  - **confirm button:** only enables if date and time are in the future.
- **Patient profile:** 
  - **assigned doctor section:** only visible if patient has a doctor assigned.
  - **appointments section:** only visible if patient has appointments.

## 9. FRONTEND ASSUMPTIONS TO AVOID
- **Do not assume a user exists without checking the backend.**
- **Do not assume a patient has a doctor assigned without checking the backend.**
- **Do not assume an appointment can be created without checking for conflicts.**