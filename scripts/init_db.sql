-- Inicialización de base de datos MySQL para Agente Solar Inteligente
CREATE DATABASE IF NOT EXISTS agente_solar_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Crear usuario si no existe (compatible con MySQL 5.7+ y 8+)
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '';
GRANT ALL PRIVILEGES ON agente_solar_db.* TO 'root'@'%';
FLUSH PRIVILEGES;

USE agente_solar_db;
