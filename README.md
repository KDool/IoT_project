# IoT Project

## Install Docker Compose

Docker Compose requires Docker. The recommended setup is **Docker Engine + the Compose plugin** (Compose v2).

### Ubuntu / Debian (Linux)/ WSL
1. Install Docker Engine (if you don’t already have it) and the Compose plugin:
   - `sudo apt-get update`
   - `sudo apt-get install -y docker.io docker-compose-plugin`
2. Verify:
   - `docker compose version`

If you get “permission denied” talking to the Docker daemon:
- `sudo usermod -aG docker $USER` then log out/in (or reboot).

## Run the infrastructure

The infrastructure is defined in `infrastructure/docker-compose.yaml` and brings up:
- MySQL (`iot_mysql`) on `localhost:3306`
- Grafana (`iot_grafana`) on `http://localhost:3000`

### Start
- `cd infrastructure`
- `docker compose up -d`

### Check status / logs
- `docker compose ps`
- `docker compose logs -f`

### Stop
- `docker compose down`

### Reset (delete volumes/data)
- `docker compose down -v`

### Default credentials
- **MySQL**
  - database: `iot_des`
  - user: `iot_user`
  - password: `iot_password`
  - root password: `rootpassword`
- **Grafana**
  - user: `admin`
  - password: `adminpassword`

## Connect Grafana to MySQL (UI)

1. Open Grafana: `http://localhost:3000` and log in (`admin` / `adminpassword`).
2. Go to **Connections** → **Data sources** → **Add new data source**.
3. Select **MySQL**.
4. Configure:
   - **Host URL**: `mysql:3306` (Grafana runs in Docker; use the Compose service name)
   - **Database**: `iot_des`
   - **User**: `iot_user`
   - **Password**: `iot_password`
5. Click **Save & test**.

## Cloud application (Python / CoAP)

The CoAP demo lives in `cloud-application/` and uses `aiocoap`.

### Create virtual environment (`env`)

From the repo root:
- `cd cloud-application`
- `python3 -m venv env`

Activate it:
- macOS/Linux/WSL: `source env/bin/activate`
- Windows (PowerShell): `.\env\Scripts\Activate.ps1`

### Install dependencies

With the venv activated:
- `python -m pip install --upgrade pip`
- `pip install -r requirements.txt`

### Test `server.py` and `client.py`

In terminal 1 (starts a CoAP server on localhost):
- `cd cloud-application`
- `source env/bin/activate` (or Windows activate command above)
- `python server.py`

In terminal 2 (runs a CoAP GET to `/hello`):
- `cd cloud-application`
- `source env/bin/activate` (or Windows activate command above)
- `python client.py`

Expected output from `client.py`:
- `Hello`
