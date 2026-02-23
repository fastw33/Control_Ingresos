/* === Ajustes en la tabla MARCACION === */
-- 1) Añadir columna para la justificación (hasta 500 caracteres, opcional)
ALTER TABLE marcacion
    ADD COLUMN justificacion VARCHAR(500) NULL AFTER observacion;

-- 2) Añadir columna para la URL de evidencia (opcional)
ALTER TABLE marcacion
    ADD COLUMN evidencia_url VARCHAR(255) NULL AFTER justificacion;

-- 3) Añadir columna para el estado de aprobación (puede ser NULL para indicar “pendiente”, 0 = no aprobado, 1 = aprobado)
ALTER TABLE marcacion
    ADD COLUMN aprobado TINYINT(1) NULL DEFAULT NULL AFTER evidencia_url;


/* === Ajustes en la tabla PERSONAL === */
-- 4) Eliminar la columna que almacena horas semanales (si ya no la necesitas)
ALTER TABLE personal
    DROP COLUMN horas_semana;

-- 5) Añadir columnas para el horario de entrada y de salida (opcional)
ALTER TABLE personal
    ADD COLUMN horario_int TIME NULL AFTER estado,
    ADD COLUMN horario_off TIME NULL AFTER horario_int;
