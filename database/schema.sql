-- WorkForce AI Pro – MySQL 8 schema (generated from SQLAlchemy models)

CREATE DATABASE IF NOT EXISTS workforce_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE workforce_ai;
SET FOREIGN_KEY_CHECKS=0;

CREATE TABLE departments (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(255), 
	budget FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE leave_policies (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	leave_type VARCHAR(30) NOT NULL, 
	annual_quota INTEGER NOT NULL, 
	carry_forward BOOL NOT NULL, 
	description VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (leave_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE shifts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(60) NOT NULL, 
	start_time TIME NOT NULL, 
	end_time TIME NOT NULL, 
	standard_hours FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE job_roles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	title VARCHAR(100) NOT NULL, 
	department_id INTEGER, 
	level INTEGER NOT NULL, 
	min_salary FLOAT NOT NULL, 
	max_salary FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_title_dept UNIQUE (title, department_id), 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_job_roles_department_id ON job_roles (department_id);

CREATE TABLE employees (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_code VARCHAR(20) NOT NULL, 
	first_name VARCHAR(80) NOT NULL, 
	last_name VARCHAR(80) NOT NULL, 
	email VARCHAR(190) NOT NULL, 
	phone VARCHAR(30), 
	gender VARCHAR(15), 
	age INTEGER NOT NULL, 
	marital_status VARCHAR(15) NOT NULL, 
	education INTEGER NOT NULL, 
	address VARCHAR(255), 
	department_id INTEGER, 
	role_id INTEGER, 
	manager_id INTEGER, 
	shift_id INTEGER, 
	hire_date DATE NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	termination_date DATE, 
	monthly_salary FLOAT NOT NULL, 
	job_level INTEGER NOT NULL, 
	distance_from_home FLOAT NOT NULL, 
	years_at_company FLOAT NOT NULL, 
	years_since_promotion FLOAT NOT NULL, 
	total_working_years FLOAT NOT NULL, 
	num_companies_worked INTEGER NOT NULL, 
	overtime BOOL NOT NULL, 
	job_satisfaction INTEGER NOT NULL, 
	environment_satisfaction INTEGER NOT NULL, 
	work_life_balance INTEGER NOT NULL, 
	training_times_last_year INTEGER NOT NULL, 
	performance_rating INTEGER NOT NULL, 
	stock_option_level INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(role_id) REFERENCES job_roles (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(shift_id) REFERENCES shifts (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_emp_dept_status ON employees (department_id, status);
CREATE INDEX ix_employees_department_id ON employees (department_id);
CREATE UNIQUE INDEX ix_employees_email ON employees (email);
CREATE UNIQUE INDEX ix_employees_employee_code ON employees (employee_code);
CREATE INDEX ix_employees_manager_id ON employees (manager_id);
CREATE INDEX ix_employees_role_id ON employees (role_id);
CREATE INDEX ix_employees_status ON employees (status);

CREATE TABLE activity_events (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER, 
	event_type VARCHAR(40) NOT NULL, 
	description VARCHAR(300) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	payload JSON, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_activity_events_created_at ON activity_events (created_at);
CREATE INDEX ix_activity_events_employee_id ON activity_events (employee_id);

CREATE TABLE alerts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER, 
	alert_type VARCHAR(30) NOT NULL, 
	severity VARCHAR(10) NOT NULL, 
	message VARCHAR(500) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	created_at DATETIME NOT NULL, 
	resolved_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_alerts_employee_id ON alerts (employee_id);
CREATE INDEX ix_alerts_status ON alerts (status);

CREATE TABLE attendance (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	work_date DATE NOT NULL, 
	check_in DATETIME, 
	check_out DATETIME, 
	working_hours FLOAT NOT NULL, 
	overtime_hours FLOAT NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_att_emp_date UNIQUE (employee_id, work_date), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_att_date ON attendance (work_date);

CREATE TABLE goals (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description VARCHAR(500), 
	progress INTEGER NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	due_date DATE, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_goals_employee_id ON goals (employee_id);

CREATE TABLE monitoring_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	event VARCHAR(40) NOT NULL, 
	old_score FLOAT, 
	new_score FLOAT NOT NULL, 
	old_level VARCHAR(10), 
	new_level VARCHAR(10) NOT NULL, 
	`trigger` VARCHAR(40) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_monitoring_logs_created_at ON monitoring_logs (created_at);
CREATE INDEX ix_monitoring_logs_employee_id ON monitoring_logs (employee_id);

CREATE TABLE payroll (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	basic FLOAT NOT NULL, 
	hra FLOAT NOT NULL, 
	allowances FLOAT NOT NULL, 
	overtime_pay FLOAT NOT NULL, 
	bonus FLOAT NOT NULL, 
	incentive FLOAT NOT NULL, 
	gross FLOAT NOT NULL, 
	tax FLOAT NOT NULL, 
	pf_deduction FLOAT NOT NULL, 
	other_deductions FLOAT NOT NULL, 
	total_deductions FLOAT NOT NULL, 
	net_pay FLOAT NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	generated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_payroll_emp_period UNIQUE (employee_id, month, year), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_payroll_employee_id ON payroll (employee_id);
CREATE INDEX ix_payroll_period ON payroll (year, month);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	email VARCHAR(190) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	is_active BOOL NOT NULL, 
	employee_id INTEGER, 
	last_login DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (employee_id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_role ON users (`role`);

CREATE TABLE audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	user_email VARCHAR(190), 
	action VARCHAR(40) NOT NULL, 
	entity VARCHAR(50) NOT NULL, 
	entity_id VARCHAR(50), 
	changes JSON, 
	ip_address VARCHAR(45), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX ix_audit_logs_entity ON audit_logs (entity);
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE chat_messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sender_id INTEGER NOT NULL, 
	receiver_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	is_read BOOL NOT NULL, 
	read_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sender_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(receiver_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_chat_pair ON chat_messages (sender_id, receiver_id, created_at);
CREATE INDEX ix_chat_recv_read ON chat_messages (receiver_id, is_read);

CREATE TABLE datasets (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	version INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	stored_path VARCHAR(400) NOT NULL, 
	rows_total INTEGER NOT NULL, 
	rows_valid INTEGER NOT NULL, 
	rows_failed INTEGER NOT NULL, 
	rows_duplicate INTEGER NOT NULL, 
	attrition_rate FLOAT NOT NULL, 
	failed_report JSON, 
	status VARCHAR(15) NOT NULL, 
	uploaded_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_dataset_version UNIQUE (name, version), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_datasets_name ON datasets (name);

CREATE TABLE documents (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	doc_type VARCHAR(40) NOT NULL, 
	original_name VARCHAR(255) NOT NULL, 
	stored_name VARCHAR(255) NOT NULL, 
	content_type VARCHAR(100) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	uploaded_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	UNIQUE (stored_name), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_documents_employee_id ON documents (employee_id);

CREATE TABLE leave_requests (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	leave_type VARCHAR(30) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	days INTEGER NOT NULL, 
	reason VARCHAR(500), 
	status VARCHAR(15) NOT NULL, 
	reviewed_by INTEGER, 
	review_comment VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_leave_requests_employee_id ON leave_requests (employee_id);
CREATE INDEX ix_leave_requests_status ON leave_requests (status);

CREATE TABLE notifications (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	message VARCHAR(600) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	priority VARCHAR(10) NOT NULL, 
	is_read BOOL NOT NULL, 
	link VARCHAR(200), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_notif_user_read ON notifications (user_id, is_read);

CREATE TABLE password_reset_tokens (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	used BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (token_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE TABLE performance_reviews (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	reviewer_id INTEGER, 
	period VARCHAR(20) NOT NULL, 
	rating INTEGER NOT NULL, 
	strengths VARCHAR(500), 
	improvements VARCHAR(500), 
	comments VARCHAR(1000), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_performance_reviews_employee_id ON performance_reviews (employee_id);

CREATE TABLE tasks (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	assigned_to INTEGER, 
	created_by INTEGER, 
	employee_id INTEGER, 
	priority VARCHAR(10) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	due_date DATE, 
	created_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_tasks_assigned_to ON tasks (assigned_to);
CREATE INDEX ix_tasks_due_date ON tasks (due_date);
CREATE INDEX ix_tasks_status ON tasks (status);

CREATE TABLE ml_models (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER, 
	algorithm VARCHAR(60) NOT NULL, 
	accuracy FLOAT NOT NULL, 
	precision_score FLOAT NOT NULL, 
	recall FLOAT NOT NULL, 
	f1 FLOAT NOT NULL, 
	roc_auc FLOAT NOT NULL, 
	cv_roc_auc FLOAT NOT NULL, 
	train_rows INTEGER NOT NULL, 
	feature_importance JSON, 
	comparison JSON, 
	confusion JSON, 
	artifact_path VARCHAR(400) NOT NULL, 
	is_active BOOL NOT NULL, 
	trained_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES datasets (id) ON DELETE SET NULL, 
	FOREIGN KEY(trained_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_ml_models_is_active ON ml_models (is_active);

CREATE TABLE predictions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	model_id INTEGER, 
	risk_score FLOAT NOT NULL, 
	risk_level VARCHAR(10) NOT NULL, 
	confidence FLOAT NOT NULL, 
	top_factors JSON, 
	`trigger` VARCHAR(40) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(model_id) REFERENCES ml_models (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_pred_emp_time ON predictions (employee_id, created_at);

CREATE TABLE interventions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	prediction_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	recommendation TEXT NOT NULL, 
	priority VARCHAR(10) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	outcome VARCHAR(20), 
	assigned_to INTEGER, 
	follow_up_date DATE, 
	auto_generated BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	closed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(prediction_id) REFERENCES predictions (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_interventions_employee_id ON interventions (employee_id);
CREATE INDEX ix_interventions_status ON interventions (status);

CREATE TABLE intervention_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	intervention_id INTEGER NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	note VARCHAR(500), 
	user_id INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(intervention_id) REFERENCES interventions (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_intervention_logs_intervention_id ON intervention_logs (intervention_id);

SET FOREIGN_KEY_CHECKS=1;