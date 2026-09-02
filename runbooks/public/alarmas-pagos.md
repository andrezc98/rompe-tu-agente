# Alarmas del equipo de pagos

## aws-cdarg-sentinel-alarm-dev
Alarma de ambiente dev (instancia aws-cdarg-sentinel-ec2-dev). Umbral: CPUUtilization. Primer paso: revisar la
métrica de los últimos 30 minutos con get_metric. Si el promedio supera 80%
durante 15 minutos, abrir ticket CHG y evaluar reinicio (ver
reinicio-instancias.md).

## StatusCheckFailed
Si StatusCheckFailed_Instance es 1, la instancia no responde al sistema
operativo. No reiniciar sin ticket de cambio.
