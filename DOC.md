# Documentacion de la API ROS 2 para UR3e

Este documento describe como funciona el paquete `ur3e_api`, que servicios expone y como integrarlo desde otra aplicacion ROS 2. La API envuelve la clase `Robot` de `robot.py` y la publica como un nodo ROS 2 llamado `/ur3e_api`.

## Resumen rapido

- Paquete ROS 2: `ur3e_api`
- Nodo: `/ur3e_api`
- Ejecutable: `ur3e_api_node`
- Robot soportado: UR3e controlado por RTDE
- Middleware: ROS 2 Humble
- Lenguaje del nodo: Python con `rclpy`
- Dependencia para conectar al robot real: `ur_rtde`, que proporciona `rtde_control` y `rtde_receive`

El nodo puede arrancar sin conectarse al robot. Esto permite probar servicios locales como `/get_pos_init`, `/get_pos_ref` y `/get_aprox`. Para leer estado real o mover el robot, primero hay que instalar `ur_rtde` y llamar a `/connect`.

## Unidades y convenciones

Todas las poses TCP usan el formato de Universal Robots:

```text
[x, y, z, rx, ry, rz]
```

- `x`, `y`, `z`: metros
- `rx`, `ry`, `rz`: radianes, como vector de rotacion
- juntas: radianes
- velocidades y aceleraciones de los servicios de movimiento: porcentaje de 0 a 100 segun la escala interna de `robot.py`

Ejemplos:

```text
0.005  = 5 mm
-0.010 = -10 mm
1.5708 = 90 grados aproximadamente
```

## Seguridad operacional

Antes de ejecutar comandos de movimiento:

1. Verifica que el robot esta conectado con `/check_connection`.
2. Lee la pose actual con `/get_pos`.
3. Usa velocidades bajas para las primeras pruebas, por ejemplo `speed: 5.0` y `acceleration: 5.0`.
4. Mantente cerca del paro de emergencia o del teach pendant.
5. No llames a `/a_move`, `/joint_move`, `/a_speed`, `/servocontrol` o `/servocontrol_joint` con valores que no hayas validado.

Los movimientos `a_move`, `joint_move` y `offset_move` son asincronos: el servicio puede responder antes de que el robot haya terminado completamente el movimiento. Usa `/is_steady`, `/stop`, `/speed_stop` o la telemetria para supervisar el estado.

## Instalacion en Docker

Dentro de la imagen ROS 2 Humble:

```bash
cd /ros2-ur3e
source /opt/ros/humble/setup.bash
apt update
apt install -y python3-pip
python3 -m pip install ur_rtde
colcon build --symlink-install
source install/setup.bash
```

Si cambias archivos `.srv`, limpia y recompila:

```bash
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
```

## Arranque del nodo

Arranque sin conectar automaticamente:

```bash
ros2 run ur3e_api ur3e_api_node --ros-args \
  -p robot_ip:=192.168.0.101 \
  -p auto_connect:=false \
  -p refresh_rate:=1.0
```

Arranque conectando automaticamente:

```bash
ros2 run ur3e_api ur3e_api_node --ros-args \
  -p robot_ip:=192.168.0.101 \
  -p auto_connect:=true
```

Para desarrollo y pruebas es mas seguro usar `auto_connect:=false` y llamar a `/connect` manualmente.

## Parametros del nodo

| Parametro | Tipo | Valor por defecto | Descripcion |
| --- | --- | --- | --- |
| `robot_ip` | `string` | `192.168.0.10` | IP del controlador UR. No se puede cambiar mientras el robot esta conectado. |
| `auto_connect` | `bool` | `false` | Si es `true`, intenta conectar al arrancar. |
| `refresh_rate` | `double` | `1.0` | Frecuencia en Hz para publicar `/tcp_pose` y `/tcp_force`. |

Cambiar frecuencia de telemetria en caliente:

```bash
ros2 param set /ur3e_api refresh_rate 5.0
```

Cambiar IP solo si no hay conexion activa:

```bash
ros2 param set /ur3e_api robot_ip 192.168.0.101
```

## Topics publicados

### `/tcp_pose`

Tipo:

```text
std_msgs/msg/Float64MultiArray
```

Contenido:

```text
[x, y, z, rx, ry, rz]
```

Publica la pose TCP actual leida desde RTDE. Solo publica cuando el robot esta conectado.

Ejemplo:

```bash
ros2 topic echo /tcp_pose
```

### `/tcp_force`

Tipo:

```text
std_msgs/msg/Float64MultiArray
```

Contenido:

```text
[fx, fy, fz, tx, ty, tz]
```

Publica la fuerza/par TCP actual leida desde RTDE. Solo publica cuando el robot esta conectado.

Ejemplo:

```bash
ros2 topic echo /tcp_force
```

## Modelo general de respuestas

Casi todos los servicios devuelven:

```text
bool success
string message
```

Convencion:

- `success: true`, `message: "ok"` o equivalente: la llamada se ejecuto correctamente.
- `success: false`: la llamada fallo. `message` contiene la razon devuelta por la excepcion o por la validacion.

Para integrar desde otra aplicacion, comprueba siempre `response.success` antes de continuar con la siguiente accion.

## Servicios de estado y conexion

Estos servicios usan `std_srvs/srv/Trigger`.

### `/connect`

Conecta RTDE de control y recepcion con la IP configurada en `robot_ip`.

```bash
ros2 service call /connect std_srvs/srv/Trigger "{}"
```

Respuesta esperada:

```text
success: true
message: connected
```

Si `ur_rtde` no esta instalado, el servicio fallara con un mensaje indicando que falta instalarlo.

### `/reconnect`

Intenta desconectar las interfaces RTDE existentes y conectar de nuevo.

```bash
ros2 service call /reconnect std_srvs/srv/Trigger "{}"
```

Usalo si el robot reinicio, cambio de estado o se perdio la conexion.

### `/check_connection`

Comprueba si las dos interfaces RTDE estan conectadas.

```bash
ros2 service call /check_connection std_srvs/srv/Trigger "{}"
```

Posibles respuestas:

```text
success: true
message: connected
```

```text
success: false
message: not connected
```

### `/is_steady`

Comprueba si el robot esta quieto segun RTDE.

```bash
ros2 service call /is_steady std_srvs/srv/Trigger "{}"
```

Respuesta:

```text
success: true
message: steady
```

o:

```text
success: false
message: moving
```

### `/stop`

Ejecuta una parada articular mediante `stopJ`.

```bash
ros2 service call /stop std_srvs/srv/Trigger "{}"
```

Usalo para detener movimientos asincronos como `/a_move`, `/joint_move` u `/offset_move`.

### `/speed_stop`

Detiene un movimiento de velocidad iniciado con `/a_speed`.

```bash
ros2 service call /speed_stop std_srvs/srv/Trigger "{}"
```

### `/freedrive_on`

Activa modo freedrive con ejes libres `[1, 1, 1, 0, 0, 0]`.

```bash
ros2 service call /freedrive_on std_srvs/srv/Trigger "{}"
```

### `/freedrive_off`

Desactiva el modo freedrive.

```bash
ros2 service call /freedrive_off std_srvs/srv/Trigger "{}"
```

### `/end_servocontrol`

Termina el modo servo con `servoStop`.

```bash
ros2 service call /end_servocontrol std_srvs/srv/Trigger "{}"
```

## Servicios de lectura vectorial

Estos servicios usan `ur3e_api/srv/GetVector`:

```text
---
bool success
string message
float64[] values
```

### `/get_pos`

Devuelve la pose TCP actual:

```text
[x, y, z, rx, ry, rz]
```

Ejemplo:

```bash
ros2 service call /get_pos ur3e_api/srv/GetVector "{}"
```

### `/get_joints`

Devuelve las posiciones articulares actuales:

```text
[j0, j1, j2, j3, j4, j5]
```

Ejemplo:

```bash
ros2 service call /get_joints ur3e_api/srv/GetVector "{}"
```

### `/get_pos_init`

Devuelve la pose inicial configurada en `robot.py` o en la variable de entorno `POS_INIT`.

```bash
ros2 service call /get_pos_init ur3e_api/srv/GetVector "{}"
```

Este servicio no necesita conexion al robot porque lee configuracion local.

### `/get_pos_ref`

Devuelve la pose de referencia configurada en `robot.py` o en la variable de entorno `POS_REF`.

```bash
ros2 service call /get_pos_ref ur3e_api/srv/GetVector "{}"
```

Este servicio no necesita conexion al robot porque lee configuracion local.

### `/get_force` y `/get_fuerzas`

Ambos llaman a la misma funcion interna `Robot.get_fuerzas()` y devuelven la fuerza/par TCP:

```text
[fx, fy, fz, tx, ty, tz]
```

Ejemplos:

```bash
ros2 service call /get_force ur3e_api/srv/GetVector "{}"
ros2 service call /get_fuerzas ur3e_api/srv/GetVector "{}"
```

## Servicios de movimiento

Los servicios de movimiento requieren conexion RTDE activa. Comprueba antes:

```bash
ros2 service call /check_connection std_srvs/srv/Trigger "{}"
```

### `/a_move`

Tipo:

```text
ur3e_api/srv/MovePose
```

Definicion:

```text
float64[] pose
float64 speed
float64 acceleration
---
bool success
string message
```

Mueve el TCP a una pose absoluta usando `moveJ_IK`.

Ejemplo:

```bash
ros2 service call /a_move ur3e_api/srv/MovePose \
  "{pose: [-0.192, -0.18212, 0.17233, 2.889, -1.211, 0.051], speed: 5.0, acceleration: 5.0}"
```

Notas:

- `pose` debe tener exactamente 6 valores.
- `x`, `y`, `z` estan en metros.
- `rx`, `ry`, `rz` estan en radianes.
- Si `speed` o `acceleration` son menores que `1`, `robot.py` los sube a `1`.

### `/offset_move`

Tipo:

```text
ur3e_api/srv/MoveOffset
```

Definicion:

```text
float64[] offset
float64 speed
float64 acceleration
---
bool success
string message
float64[] target_pose
```

Lee la pose TCP actual, suma un offset y llama internamente a `a_move`.

El offset puede tener 3 o 6 valores:

```text
[dx, dy, dz]
[dx, dy, dz, drx, dry, drz]
```

Ejemplo: mover 5 mm en X positivo y 10 mm en Y negativo:

```bash
ros2 service call /offset_move ur3e_api/srv/MoveOffset \
  "{offset: [0.005, -0.010, 0.0], speed: 5.0, acceleration: 5.0}"
```

Ejemplo con rotacion:

```bash
ros2 service call /offset_move ur3e_api/srv/MoveOffset \
  "{offset: [0.005, -0.010, 0.0, 0.0, 0.0, 0.02], speed: 5.0, acceleration: 5.0}"
```

La respuesta incluye `target_pose`, que es la pose absoluta calculada y enviada al robot:

```text
success: true
message: ok
target_pose: [...]
```

### `/joint_move`

Tipo:

```text
ur3e_api/srv/MoveJoints
```

Definicion:

```text
float64[] joints
float64 speed
float64 acceleration
---
bool success
string message
```

Mueve el robot a una configuracion articular absoluta con `moveJ`.

Ejemplo:

```bash
ros2 service call /joint_move ur3e_api/srv/MoveJoints \
  "{joints: [0.0, -1.57, 1.57, -1.57, -1.57, 0.0], speed: 5.0, acceleration: 5.0}"
```

`joints` debe tener exactamente 6 valores en radianes.

### `/a_speed`

Tipo:

```text
ur3e_api/srv/SpeedCommand
```

Definicion:

```text
float64[] vector
float64 speed
float64 acceleration
float64 duration
---
bool success
string message
```

Inicia un movimiento cartesiano de velocidad con `speedL`.

Ejemplo: mover en Z positivo durante 0.25 segundos:

```bash
ros2 service call /a_speed ur3e_api/srv/SpeedCommand \
  "{vector: [0.0, 0.0, 1.0, 0.0, 0.0, 0.0], speed: 1.0, acceleration: 5.0, duration: 0.25}"
```

Despues de usar `/a_speed`, llama a `/speed_stop`:

```bash
ros2 service call /speed_stop std_srvs/srv/Trigger "{}"
```

### `/servocontrol`

Tipo:

```text
ur3e_api/srv/Servo
```

Definicion:

```text
float64[] coordinates
---
bool success
string message
```

Ejecuta `servoL` con una pose cartesiana.

Ejemplo:

```bash
ros2 service call /servocontrol ur3e_api/srv/Servo \
  "{coordinates: [-0.192, -0.182, 0.172, 2.889, -1.211, 0.051]}"
```

Este servicio esta pensado para control servo repetido. Al terminar, llama a:

```bash
ros2 service call /end_servocontrol std_srvs/srv/Trigger "{}"
```

### `/servocontrol_joint`

Tipo:

```text
ur3e_api/srv/Servo
```

Usa el mismo mensaje que `/servocontrol`, pero interpreta `coordinates` como juntas y llama a `servoJ`.

Ejemplo:

```bash
ros2 service call /servocontrol_joint ur3e_api/srv/Servo \
  "{coordinates: [0.0, -1.57, 1.57, -1.57, -1.57, 0.0]}"
```

Al terminar:

```bash
ros2 service call /end_servocontrol std_srvs/srv/Trigger "{}"
```

## Servicio auxiliar de aproximacion

### `/get_aprox`

Tipo:

```text
ur3e_api/srv/GetAprox
```

Definicion:

```text
float64[] pose
---
bool success
string message
float64[] pose
```

Devuelve una pose de aproximacion sumando `ALTURA_SEGURIDAD` al eje Z. Por defecto `ALTURA_SEGURIDAD` es `0.021` m.

Ejemplo:

```bash
ros2 service call /get_aprox ur3e_api/srv/GetAprox \
  "{pose: [0.1, 0.2, 0.3, 2.8, -1.2, 0.0]}"
```

Respuesta esperada con la altura por defecto:

```text
pose: [0.1, 0.2, 0.321, 2.8, -1.2, 0.0]
```

Este servicio no necesita conexion al robot.

## Variables de entorno soportadas

`robot.py` lee estas variables al crear `Robot`:

| Variable | Formato | Descripcion |
| --- | --- | --- |
| `VECTOR_ROTACION` | `"2.883,-1.209,0.059"` | Vector de rotacion de referencia. |
| `ALTURA_SEGURIDAD` | `"0.021"` | Altura sumada por `/get_aprox`. |
| `POS_INIT` | `"x,y,z,rx,ry,rz"` | Pose inicial devuelta por `/get_pos_init`. |
| `POS_REF` | `"x,y,z,rx,ry,rz"` | Pose de referencia devuelta por `/get_pos_ref`. |

Ejemplo:

```bash
export ALTURA_SEGURIDAD=0.030
export POS_INIT="-0.192,-0.18212,0.17233,2.889,-1.211,0.051"
ros2 run ur3e_api ur3e_api_node --ros-args -p robot_ip:=192.168.0.101
```

## Flujo recomendado para una aplicacion cliente

1. Esperar a que existan los servicios necesarios.
2. Llamar a `/connect`.
3. Confirmar `/check_connection`.
4. Leer `/get_pos` y `/get_joints`.
5. Ejecutar movimientos pequenos y validados.
6. Supervisar `/tcp_pose`, `/tcp_force` o `/is_steady`.
7. En caso de error o parada manual, llamar a `/stop` o `/speed_stop` segun el tipo de movimiento.

## Integracion desde Python con rclpy

Ejemplo minimo para llamar a `/offset_move` desde otra aplicacion ROS 2:

```python
import rclpy
from rclpy.node import Node
from ur3e_api.srv import MoveOffset


class OffsetClient(Node):
    def __init__(self):
        super().__init__("offset_client")
        self.client = self.create_client(MoveOffset, "/offset_move")

    def move_offset(self, offset, speed=5.0, acceleration=5.0):
        if not self.client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError("El servicio /offset_move no esta disponible")

        request = MoveOffset.Request()
        request.offset = offset
        request.speed = speed
        request.acceleration = acceleration

        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        response = future.result()

        if response is None:
            raise RuntimeError("No se recibio respuesta de /offset_move")
        if not response.success:
            raise RuntimeError(response.message)

        return list(response.target_pose)


def main():
    rclpy.init()
    node = OffsetClient()
    try:
        target_pose = node.move_offset([0.005, -0.010, 0.0])
        node.get_logger().info(f"Pose objetivo: {target_pose}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

## Integracion desde linea de comandos

Secuencia completa de prueba:

```bash
cd /ros2-ur3e
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 node list
ros2 service list
ros2 service call /connect std_srvs/srv/Trigger "{}"
ros2 service call /check_connection std_srvs/srv/Trigger "{}"
ros2 service call /get_pos ur3e_api/srv/GetVector "{}"
ros2 service call /offset_move ur3e_api/srv/MoveOffset "{offset: [0.005, -0.010, 0.0], speed: 5.0, acceleration: 5.0}"
ros2 service call /is_steady std_srvs/srv/Trigger "{}"
```

## Relacion entre servicios y `robot.py`

| Servicio ROS 2 | Metodo `Robot` |
| --- | --- |
| `/connect` | `connect()` |
| `/reconnect` | `reconnect()` |
| `/check_connection` | `check_connection()` |
| `/is_steady` | `is_steady()` |
| `/stop` | `stop()` |
| `/speed_stop` | `speed_stop()` |
| `/end_servocontrol` | `end_servocontrol()` |
| `/freedrive_on` | `freedrive_on()` |
| `/freedrive_off` | `freedrive_off()` |
| `/get_pos` | `get_pos()` |
| `/get_joints` | `get_joints()` |
| `/get_pos_init` | `get_pos_init()` |
| `/get_pos_ref` | `get_pos_ref()` |
| `/get_force`, `/get_fuerzas` | `get_fuerzas()` |
| `/a_move` | `a_move()` |
| `/offset_move` | `offset_move()` |
| `/joint_move` | `joint_move()` |
| `/a_speed` | `a_speed()` |
| `/servocontrol` | `servocontrol()` |
| `/servocontrol_joint` | `servocontrol_joint()` |
| `/get_aprox` | `get_aprox()` |

## Notas de implementacion

- El nodo usa un `Lock` para serializar las llamadas a RTDE. Esto evita llamadas concurrentes desde varios servicios al mismo objeto `Robot`.
- La importacion de `rtde_control` y `rtde_receive` ocurre dentro de `Robot.connect()`. Asi se puede arrancar el nodo aunque `ur_rtde` no este instalado, siempre que no se intente conectar.
- `rosidl_generate_interfaces()` genera el paquete Python `ur3e_api.srv`. Por eso el codigo del nodo vive en `ur3e_api_node` y no en un paquete Python llamado tambien `ur3e_api`.
- `offset_move` calcula una pose absoluta y reutiliza `a_move`, por lo que hereda su comportamiento asincrono.
- Los servicios de lectura local como `/get_pos_init`, `/get_pos_ref` y `/get_aprox` pueden usarse sin conexion RTDE.

## Diagnostico rapido

Ver servicios:

```bash
ros2 service list | sort
```

Ver definicion de un servicio:

```bash
ros2 interface show ur3e_api/srv/MoveOffset
```

Ver parametros:

```bash
ros2 param list /ur3e_api
ros2 param get /ur3e_api robot_ip
```

Si `/connect` falla:

1. Comprueba que `ur_rtde` esta instalado:

```bash
python3 -c "import rtde_control, rtde_receive; print('ok')"
```

2. Comprueba red hacia el robot:

```bash
ping 192.168.0.101
```

3. Comprueba que el robot permite RTDE y que la IP usada en `robot_ip` es correcta.

