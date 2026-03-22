# FRONTEND_CONTRACT.md

## 1. SYSTEM CAPABILITIES SUMMARY

* Admin can create Patient
* Admin can update Patient
* Admin can delete Patient
* Receptionist can create Patient
* Receptionist can update Patient
* Receptionist can delete Patient
* Admin can list Patients
* Receptionist can list Patients

## 2. API ENDPOINTS

### Patient List Endpoint
* URL Pattern: `/patients/`
* HTTP Method: GET
* Who can call it: Admin, Receptionist
* Authentication required: yes, via token in Authorization header
* Request body fields: none
* Response body on success:
	+ id (integer)
	+ first_name (string)
	+ last_name (string)
	+ date_of_birth (date)
	+ gender (string, one of 'M' or 'F')
	+ phone_number (string)
	+ email (string)
	+ address (string)
	+ created_at (datetime)
	+ updated_at (datetime)
* Response body on failure: JSON error object with message
* HTTP status codes returned: 200 OK, 401 Unauthorized, 403 Forbidden

### Patient Create Endpoint
* URL Pattern: `/patients/`
* HTTP Method: POST
* Who can call it: Admin, Receptionist
* Authentication required: yes, via token in Authorization header
* Request body fields:
	+ first_name (string, required)
	+ last_name (string, required)
	+ date_of_birth (date, required)
	+ gender (string, one of 'M' or 'F', required)
	+ phone_number (string, required)
	+ email (string, optional)
	+ address (string, optional)
* Response body on success:
	+ id (integer)
	+ first_name (string)
	+ last_name (string)
	+ date_of_birth (date)
	+ gender (string, one of 'M' or 'F')
	+ phone_number (string)
	+ email (string)
	+ address (string)
	+ created_at (datetime)
	+ updated_at (datetime)
* Response body on failure: JSON error object with message
* HTTP status codes returned: 201 Created, 401 Unauthorized, 403 Forbidden, 400 Bad Request

### Patient Update Endpoint
* URL Pattern: `/patients/{id}/`
* HTTP Method: PUT
* Who can call it: Admin, Receptionist
* Authentication required: yes, via token in Authorization header
* Request body fields:
	+ first_name (string, optional)
	+ last_name (string, optional)
	+ date_of_birth (date, optional)
	+ gender (string, one of 'M' or 'F', optional)
	+ phone_number (string, optional)
	+ email (string, optional)
	+ address (string, optional)
* Response body on success:
	+ id (integer)
	+ first_name (string)
	+ last_name (string)
	+ date_of_birth (date)
	+ gender (string, one of 'M' or 'F')
	+ phone_number (string)
	+ email (string)
	+ address (string)
	+ created_at (datetime)
	+ updated_at (datetime)
* Response body on failure: JSON error object with message
* HTTP status codes returned: 200 OK, 401 Unauthorized, 403 Forbidden, 400 Bad Request

### Patient Delete Endpoint
* URL Pattern: `/patients/{id}/`
* HTTP Method: DELETE
* Who can call it: Admin, Receptionist
* Authentication required: yes, via token in Authorization header
* Request body fields: none
* Response body on success: none
* Response body on failure: JSON error object with message
* HTTP status codes returned: 204 No Content, 401 Unauthorized, 403 Forbidden

## 3. DATA CONTRACTS

### Patient Entity
* Fields:
	+ id (integer, read-only)
	+ first_name (string, required)
	+ last_name (string, required)
	+ date_of_birth (date, required)
	+ gender (string, one of 'M' or 'F', required)
	+ phone_number (string, required)
	+ email (string, optional)
	+ address (string, optional)
	+ created_at (datetime, read-only)
	+ updated_at (datetime, read-only)
* Field format constraints:
	+ phone_number: digits only
	+ date_of_birth: date format (YYYY-MM-DD)
	+ email: email format
* Fields that are read-only: id, created_at, updated_at

## 4. AUTHENTICATION & AUTHORIZATION

* Authentication works via token in Authorization header
* Token type: Bearer token
* Token must be sent in Authorization header with each request
* Role-based access is determined by IsAdminOrReceptionist permission class
* If an unauthorized request is made, a 401 Unauthorized response is returned

## 5. ROLE BASED UI RULES

### Admin Role
* Can access: all pages
* Can perform: all actions
* Cannot see or do: nothing
* UI must change based on role: display all options and features

### Receptionist Role
* Can access: patient list, patient create, patient update, patient delete
* Can perform: create, update, delete patients
* Cannot see or do: access admin-only features
* UI must change based on role: hide admin-only features and options

## 6. STATE BASED UI RULES

### Patient Entity
* UI actions available at each state:
	+ active: view, update, delete
	+ deleted: view
* Fields that become read-only at each state:
	+ active: none
	+ deleted: all fields
* Transitions the UI must support:
	+ active -> deleted (via delete action)
* Transitions the UI must explicitly prevent:
	+ deleted -> active (prevent undelete)

## 7. FORM REQUIREMENTS

### Patient Create Form
* Fields:
	+ first_name (string, required)
	+ last_name (string, required)
	+ date_of_birth (date, required)
	+ gender (string, one of 'M' or 'F', required)
	+ phone_number (string, required)
	+ email (string, optional)
	+ address (string, optional)
* Field types and formats:
	+ first_name: text input
	+ last_name: text input
	+ date_of_birth: date input
	+ gender: select input with options 'M' and 'F'
	+ phone_number: text input with digits only
	+ email: email input
	+ address: text input
* Validation rules:
	+ date_of_birth: must be in the past
	+ phone_number: must contain only digits
* Success behavior: redirect to patient list page
* Error handling behavior: display error messages

### Patient Update Form
* Fields:
	+ first_name (string, optional)
	+ last_name (string, optional)
	+ date_of_birth (date, optional)
	+ gender (string, one of 'M' or 'F', optional)
	+ phone_number (string, optional)
	+ email (string, optional)
	+ address (string, optional)
* Field types and formats:
	+ first_name: text input
	+ last_name: text input
	+ date_of_birth: date input
	+ gender: select input with options 'M' and 'F'
	+ phone_number: text input with digits only
	+ email: email input
	+ address: text input
* Validation rules:
	+ date_of_birth: must be in the past
	+ phone_number: must contain only digits
* Success behavior: redirect to patient list page
* Error handling behavior: display error messages

## 8. ERROR HANDLING

### Patient Create Endpoint
* Possible errors:
	+ validation error: invalid date_of_birth
	+ validation error: invalid phone_number
	+ database error: unable to create patient
* Error response format: JSON error object with message
* HTTP status codes returned: 400 Bad Request, 500 Internal Server Error

### Patient Update Endpoint
* Possible errors:
	+ validation error: invalid date_of_birth
	+ validation error: invalid phone_number
	+ database error: unable to update patient
* Error response format: JSON error object with message
* HTTP status codes returned: 400 Bad Request, 500 Internal Server Error

### Patient Delete Endpoint
* Possible errors:
	+ database error: unable to delete patient
* Error response format: JSON error object with message
* HTTP status codes returned: 500 Internal Server Error

## 9. WORKFLOW SEQUENCES

### Patient Create Workflow
1. User clicks create patient button
2. System displays patient create form
3. User fills out form and submits
4. System validates form data
5. System creates patient and redirects to patient list page

### Patient Update Workflow
1. User clicks update patient button
2. System displays patient update form
3. User fills out form and submits
4. System validates form data
5. System updates patient and redirects to patient list page

### Patient Delete Workflow
1. User clicks delete patient button
2. System displays confirmation dialog
3. User confirms deletion
4. System deletes patient and redirects to patient list page

## 10. CONDITIONAL UI BEHAVIOR

### Patient List Page
* Fields that appear or disappear: none
* Buttons that enable or disable: delete button disables for non-admin users
* Sections visible only to certain roles: admin-only features and options

### Patient Create Form
* Fields that appear or disappear: none
* Buttons that enable or disable: submit button disables when form is invalid
* Sections visible only to certain roles: none

### Patient Update Form
* Fields that appear or disappear: none
* Buttons that enable or disable: submit button disables when form is invalid
* Sections visible only to certain roles: none

## 11. PAGINATION & LISTING BEHAVIOR

### Patient List Endpoint
* Is it paginated: no
* Pagination format: none
* Query parameters supported: none
* List response format: JSON array of patient objects

## 12. FRONTEND ASSUMPTIONS TO AVOID

* Do not assume that the patient list will always be empty
* Do not assume that the patient create form will always be valid
* Do not assume that the patient update form will always be valid
* Do not assume that the patient delete button will always be enabled
* Do not assume that the admin-only features and options will always be visible