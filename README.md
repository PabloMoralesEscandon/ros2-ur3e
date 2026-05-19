# API ROS 2 para UR3e

Este paquete expone la clase `Robot` de `robot.py` como un nodo ROS 2 y publica telemetria del TCP. Esta pensado para controlar un UR3e mediante RTDE desde ROS 2 Humble.

Para la documentacion completa de integracion, tipos de mensajes, ejemplos y notas de seguridad, consulta [DOC.md](DOC.md).

## Resumen

- Paquete: `ur3e_api`
- Nodo: `/ur3e_api`
- Ejecutable: `ur3e_api_node`
- Robot: Universal Robots UR3e
- Conexion: RTDE mediante `ur_rtde`

Las poses TCP usan el formato:

```text
[x, y, z, rx, ry, rz]
```

`x`, `y`, `z` estan en metros. `rx`, `ry`, `rz` y las juntas estan en radianes.

## Instalacion recomendada con Docker

La forma recomendada de usar este paquete es ejecutar ROS 2 Humble dentro de Docker. Asi evitas instalar ROS 2 directamente en tu sistema host y trabajas sobre una imagen oficial.

1. Instala Docker siguiendo la documentacion oficial:

   <https://docs.docker.com/engine/install/>

2. Descarga la imagen oficial de ROS 2 Humble:

```bash
docker pull osrf/ros:humble-desktop
```

La imagen `osrf/ros` esta publicada en Docker Hub:

<https://hub.docker.com/_/ros>

3. Arranca un contenedor montando este repositorio:

```bash
docker run -it --net=host --privileged \
  -v "$(pwd)":/ros2-ur3e \
  osrf/ros:humble-desktop
```

Si el repositorio esta en otra ruta, ejecuta el comando desde la carpeta del repositorio o cambia el lado izquierdo del volumen.

4. Dentro del contenedor, instala dependencias y compila:

```bash
cd /ros2-ur3e
source /opt/ros/humble/setup.bash
apt update
apt install -y python3-pip
python3 -m pip install ur_rtde
colcon build --symlink-install
source install/setup.bash
```

Si cambias archivos `.srv`, limpia antes de recompilar:

```bash
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
```

## Ejecutar el nodo

Modo recomendado para pruebas, sin conectar automaticamente:

```bash
ros2 run ur3e_api ur3e_api_node --ros-args \
  -p robot_ip:=192.168.0.101 \
  -p auto_connect:=false \
  -p refresh_rate:=1.0
```

En otra terminal:

```bash
cd /ros2-ur3e
source /opt/ros/humble/setup.bash
source install/setup.bash
```

## Parametros

- `robot_ip` (`string`, por defecto `192.168.0.10`): IP del controlador UR.
- `auto_connect` (`bool`, por defecto `false`): conecta al robot al arrancar si esta en `true`.
- `refresh_rate` (`double`, por defecto `1.0`): frecuencia de publicacion de telemetria en Hz.

Cambiar frecuencia de telemetria:

```bash
ros2 param set /ur3e_api refresh_rate 5.0
```

## Topics

- `/tcp_pose` (`std_msgs/msg/Float64MultiArray`): pose TCP actual `[x, y, z, rx, ry, rz]`.
- `/tcp_force` (`std_msgs/msg/Float64MultiArray`): fuerza/par TCP actual `[fx, fy, fz, tx, ty, tz]`.

Ejemplo:

```bash
ros2 topic echo /tcp_pose
```

## Servicios expuestos

Servicios `std_srvs/srv/Trigger`:

- `/connect`
- `/reconnect`
- `/check_connection`
- `/is_steady`
- `/stop`
- `/speed_stop`
- `/end_servocontrol`
- `/freedrive_on`
- `/freedrive_off`

Servicios de lectura con `ur3e_api/srv/GetVector`:

- `/get_pos`
- `/get_joints`
- `/get_pos_init`
- `/get_pos_ref`
- `/get_force`
- `/get_fuerzas`

Servicios de comando:

- `/a_move` (`ur3e_api/srv/MovePose`): mueve a una pose TCP absoluta.
- `/offset_move` (`ur3e_api/srv/MoveOffset`): mueve desde la pose actual aplicando un offset.
- `/joint_move` (`ur3e_api/srv/MoveJoints`): mueve a una posicion articular absoluta.
- `/a_speed` (`ur3e_api/srv/SpeedCommand`): inicia movimiento cartesiano por velocidad.
- `/servocontrol` (`ur3e_api/srv/Servo`): ejecuta `servoL`.
- `/servocontrol_joint` (`ur3e_api/srv/Servo`): ejecuta `servoJ`.
- `/get_aprox` (`ur3e_api/srv/GetAprox`): calcula una pose de aproximacion sumando altura de seguridad en Z.

## Prueba rapida

Comprobar que el nodo responde:

```bash
ros2 node list
ros2 service call /check_connection std_srvs/srv/Trigger "{}"
ros2 service call /get_pos_init ur3e_api/srv/GetVector "{}"
ros2 service call /get_aprox ur3e_api/srv/GetAprox "{pose: [0.1, 0.2, 0.3, 2.8, -1.2, 0.0]}"
```

Conectar al robot:

```bash
ros2 service call /connect std_srvs/srv/Trigger "{}"
ros2 service call /check_connection std_srvs/srv/Trigger "{}"
ros2 service call /get_pos ur3e_api/srv/GetVector "{}"
ros2 service call /get_joints ur3e_api/srv/GetVector "{}"
```

Mover 5 mm en X positivo y 10 mm en Y negativo desde la pose actual:

```bash
ros2 service call /offset_move ur3e_api/srv/MoveOffset "{offset: [0.005, -0.010, 0.0], speed: 5.0, acceleration: 5.0}"
```

Detener movimientos:

```bash
ros2 service call /speed_stop std_srvs/srv/Trigger "{}"
ros2 service call /stop std_srvs/srv/Trigger "{}"
```

## Seguridad

Antes de mover el robot, verifica `/check_connection`, lee `/get_pos` y usa velocidades bajas. Los comandos `/a_move`, `/offset_move`, `/joint_move` y `/a_speed` pueden mover fisicamente el robot, asi que valida siempre las poses y manten acceso al paro de emergencia o al teach pendant.
