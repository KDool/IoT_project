CREATE TABLE IF NOT EXISTS device_registry (
    node_id VARCHAR(50) PRIMARY KEY,
    type VARCHAR(30) NOT NULL,
    protocol VARCHAR(10) NOT NULL,
    ip_address VARCHAR(45),
    status VARCHAR(20) DEFAULT 'active',
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS telemetry_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    node_id VARCHAR(50) NOT NULL,
    voltage FLOAT,
    current FLOAT,
    power FLOAT,
    soc FLOAT,
    ml_anomaly BOOLEAN DEFAULT 0,
    sent_at DATETIME(3) NOT NULL,
    recorded_at DATETIME(3) NOT NULL,
    FOREIGN KEY (node_id) REFERENCES device_registry(node_id)
);

CREATE TABLE IF NOT EXISTS network_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    node_id VARCHAR(50) NOT NULL,
    pdr_percent FLOAT NOT NULL,
    avg_latency_ms FLOAT NOT NULL,
    throughput_5s INT NOT NULL,
    adaptive_mode VARCHAR(20) NOT NULL,
    recorded_at DATETIME(3) NOT NULL,
    FOREIGN KEY (node_id) REFERENCES device_registry(node_id)
);



INSERT IGNORE INTO device_registry (node_id, type, protocol, ip_address, status) VALUES
('prod_solar_01', 'priority_producer', 'CoAP', 'fd00::1', 'active'),
('prod_wind_01', 'priority_producer', 'MQTT', 'fd00::2', 'active'),
('acc_batt_01', 'accumulator', 'CoAP', 'fd00::3', 'active'),
('cons_hvac_01', 'consumer', 'MQTT', 'fd00::4', 'active');