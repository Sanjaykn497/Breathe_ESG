# breathe_ESG — PostgreSQL Integration & Setup Guide

Since PostgreSQL is a core requirement for this project, this guide provides a step-by-step procedure to download, install, configure, and verify your Django-to-PostgreSQL connection on Windows.

---

## Step 1: Install PostgreSQL on Windows

If PostgreSQL is not yet installed on your machine, you must install the server first:

1. **Download the Installer**:
   - Go to the official [EnterpriseDB PostgreSQL Downloads](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).
   - Select **Windows x86-64** for version **15** or **16**.
2. **Run the Installer**:
   - Double-click the downloaded `.exe` file to start installation.
   - Click **Next** on the welcome screen.
3. **Choose Installation Directory**:
   - Keep the default (`C:\Program Files\PostgreSQL\<version>`) and click **Next**.
4. **Select Components**:
   - Ensure the following are checked:
     - **PostgreSQL Server** (The database engine)
     - **pgAdmin 4** (The graphical management tool)
     - **Command Line Tools** (For `psql`)
   - Click **Next**.
5. **Set Database Password**:
   - Enter `breathe_pass` as the password for the superuser (`postgres`). 
   - *Note: Keeping this password makes it match your project's `.env` out of the box.*
6. **Set Port Number**:
   - Keep the default port `5432` and click **Next**.
7. **Complete Installation**:
   - Click **Next** through the remaining screens and click **Finish** when done.

---

## Step 2: Initialize Database and Credentials

You must create the specific database and user role required by the `breathe_ESG` configuration.

### Option A: Using pgAdmin 4 (Visual Tool)
1. Open the Windows Start menu, search for **pgAdmin 4**, and open it.
2. Expand **Servers** on the left browser tree. It will ask for your master password (use the password you created in Step 1).
3. Right-click on **Databases** → **Create** → **Database...**
   - **Database Name**: `breathe_esg`
   - Click **Save**.
4. Right-click on **Login/Group Roles** → **Create** → **Login/Group Role...**
   - **Role Name**: `breathe_user`
   - In the **Definition** tab, set **Password** to `breathe_pass`.
   - In the **Privileges** tab, toggle **Can login** to `Yes` and **Superuser** to `Yes` (for development simplicity).
   - Click **Save**.

### Option B: Using psql (Command Line Tool)
1. Open the Windows Start menu, search for **SQL Shell (psql)**, and open it.
2. Press **Enter** to accept the defaults for Server, Database, Port, and Username.
3. Type the password you set during installation (`breathe_pass`) and press **Enter**.
4. Run these SQL commands one-by-one:
   ```sql
   CREATE DATABASE breathe_esg;
   CREATE USER breathe_user WITH PASSWORD 'breathe_pass';
   GRANT ALL PRIVILEGES ON DATABASE breathe_esg TO breathe_user;
   ```

---

## Step 3: Configure Your Project `.env` File

Open [`.env`](file:///c:/Users/manju/breathe_ESG/.env) in your workspace and make sure the connection string matches:

```env
SECRET_KEY=django-insecure-change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL Connection String
DATABASE_URL=postgres://breathe_user:breathe_pass@localhost:5432/breathe_esg

# CORS Allowed Origin
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

---

## Step 4: Run Migrations Against PostgreSQL

With the PostgreSQL server active on port `5432` and your database created, run the migrations to generate all the tables:

1. Open your terminal in the project root:
   ```bash
   cd c:\Users\manju\breathe_ESG
   ```
2. Activate the virtual environment:
   ```bash
   .venv\Scripts\activate
   ```
3. Run the migrations:
   ```bash
   python manage.py migrate
   ```
   *You will see Django create all tables inside your PostgreSQL database!*

4. Create your superuser account:
   ```bash
   python manage.py createsuperuser
   ```

---

## Step 5: Start the App & Verify Connection

1. **Start the Backend Server**:
   ```bash
   python manage.py runserver
   ```
2. **Start the Frontend Client**:
   In a separate terminal:
   ```bash
   cd frontend
   npm run dev
   ```
3. **Verify in pgAdmin**:
   - Open pgAdmin 4.
   - Go to **Servers** → **PostgreSQL** → **Databases** → **breathe_esg** → **Schemas** → **public** → **Tables**.
   - You should see your tables listed: `esg_emission_record`, `esg_raw_record`, `esg_audit_log`, `org_organization`, `org_user`, and `esg_data_source`!
