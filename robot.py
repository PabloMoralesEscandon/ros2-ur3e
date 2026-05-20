import logging
import os
from time import sleep

import numpy as np
from scipy.spatial.transform import Rotation

logger = logging.getLogger(__name__)

# CONSTANTES
MAX_SPEED = 3.14  # rad/s, velocidad articular máxima
MAX_ACC = 5  # rad/s^2, aceleración articular


# FUNCIONES
def eval_float(x):
    return eval(x.strip())


# CLASES
class Robot:
    """Representa el Robot con sus funciones tanto de entrada como de salida."""

    def __init__(self, ip):
        """
        Constructor de la clase Robot. Inicializa los parámetros básicos pero no realiza la conexión.

        Args:
            ip (str): Ip del robot
        """
        # Guardamos la ip del robot
        self.ip = ip
        # Obtenemos el vector de rotación y la altura de seguridad de las variables de entorno, sino usamos valores por defecto.
        rot_vec = os.getenv("VECTOR_ROTACION", "")
        if rot_vec == "":
            R_ref0 = [2.883, -1.209, 0.059]
        else:
            R_ref0 = [eval_float(item) for item in rot_vec.split(",")]
        self.alt_seg = os.getenv("ALTURA_SEGURIDAD", "")
        if self.alt_seg == "":
            self.alt_seg = 0.021
        else:
            self.alt_seg = eval(self.alt_seg)
        self.R_ref0 = np.array(R_ref0)
        # No inciamos la conexión de entrada y salida con el robot (si no está encendido dará problemas)
        self.rtde_c = None  # (OUT)
        self.rtde_r = None  # (IN)
        self.freedrive = False

        # Obtenemos la posición inicial y la posición de referencia de las variables de entorno, sino usamos valores por defecto.
        pos_init_str = os.getenv("POS_INIT", "")
        if pos_init_str == "":
            self.pos_init = [
                -192 / 1000,
                -182.12 / 1000,
                172.33 / 1000,
                2.889,
                -1.211,
                0.051,
            ]
        else:
            self.pos_init = [eval_float(item) for item in pos_init_str.split(",")]
        pos_ref_str = os.getenv("POS_REF", "")
        if pos_ref_str == "":
            self.pos_ref = [
                -162 / 1000,
                -182.12 / 1000,
                200 / 1000,
                2.889,
                -1.211,
                0.051,
            ]
        else:
            self.pos_ref = [eval_float(item) for item in pos_ref_str.split(",")]

    def connect(self):
        """Inicia la conexión tanto de entrada como de salida del robot"""
        try:
            # Se importa aquí para poder arrancar el nodo sin RTDE si solo se prueban servicios locales.
            import rtde_control
            import rtde_receive
        except ImportError as exc:
            raise ImportError(
                "The ur_rtde Python modules are not installed. Install them in the "
                "same environment with: python3 -m pip install ur_rtde"
            ) from exc

        try:
            self.rtde_c = rtde_control.RTDEControlInterface(self.ip, 50)  # (OUT)
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.ip, 50)  # (IN)
        except Exception as exc:
            self.rtde_c = None
            self.rtde_r = None
            raise ConnectionError(f"No se ha podido conectar al robot en {self.ip}") from exc

        for i in range(10):
            if self.rtde_r.isConnected():
                break
            self.rtde_r.reconnect()
            logger.warning(
                "La conexión de recepción ha fallado, se intenta reconectar, intento %d",
                i,
            )
            sleep(1)
        else:
            raise ConnectionError(
                "No se ha podido conectar la recepción tras diez intentos."
            )

        for i in range(10):
            if self.rtde_c.isConnected():
                break
            self.rtde_c.reconnect()
            logger.warning(
                "La conexión de envío ha fallado, se intenta reconectar, intento %d", i
            )
            sleep(1)
        else:
            raise ConnectionError(
                "No se ha podido conectar el control tras diez intentos."
            )

    def check_connection(self):
        """Comprueba que el robot está conectado."""
        if self.rtde_c != None and self.rtde_r != None:
            return self.rtde_c.isConnected() and self.rtde_r.isConnected()
        else:
            return False

    def reconnect(self):
        """Desconecta el robot y vuelve a intentar conectar."""
        try:
            self.rtde_c.disconnect()
        except:
            pass
        try:
            self.rtde_r.disconnect()
        except:
            pass
        self.connect()

    def is_steady(self):
        """Comprueba si el robot está en movimiento."""
        return self.rtde_c.isSteady()

    def stop(self):
        """Detiene al robot cuando está realizando un movimiento asíncrono"""
        self.rtde_c.stopJ(a=2.0, asynchronous=True)

    def a_move(self, pose, speed, acc):
        """
        Mueve el robot de manera asincrona.

        Args:
            pose (array de floats): Coordenas a las que se debe mover el robot
            speed (float): Velocidad (de 0 a 100) del robot
            acc (float): Aceleración (de 0 a 100) del robot
        """
        # Si la velocidad o la aceleración son 0 establecerlas como 1 (sino da error)
        if speed < 1:
            speed = 1
        if acc < 1:
            acc = 1
        # Movemos a la posición a la velocidad y aceleración correspondientes
        self.rtde_c.moveJ_IK(
            pose, speed * MAX_SPEED / 100, acc * MAX_ACC / 100, True
        )  # Movimiento asíncrono

    def offset_move(self, offset, speed, acc):
        """
        Mueve el TCP desde la posición actual aplicando un offset cartesiano.

        Args:
            offset (array de floats): Offset [x, y, z] o [x, y, z, rx, ry, rz].
            speed (float): Velocidad (de 0 a 100) del robot.
            acc (float): Aceleración (de 0 a 100) del robot.
        """
        current_pose = list(self.get_pos())
        target_pose = current_pose.copy()
        # Los tres primeros valores son metros; si se pasan seis, los tres últimos son radianes.
        for index, value in enumerate(offset):
            target_pose[index] += value
        self.a_move(target_pose, speed, acc)
        return target_pose

    def joint_move(self, joint, speed, acc):
        """
        Mueve el robot de manera asincrona por posición de sus articulaciones.

        Args:
            joint (array de floats): Ángulos de articulación a los que se debe mover el robot
            speed (float): Velocidad (de 0 a 100) del robot
            acc (float): Aceleración (de 0 a 100) del robot
        """
        # Si la velocidad o la aceleración son 0 establecerlas como 1 (sino da error)
        if speed < 1:
            speed = 1
        if acc < 1:
            acc = 1
        # Movemos a la posición a la velocidad y aceleración correspondientes
        self.rtde_c.moveJ(
            joint, speed * MAX_SPEED / 100, acc * MAX_ACC / 100, True
        )  # Movimiento asíncrono

    def a_speed(self, vector, speed, acc, time):
        """
        Inicia un movimiento asíncrono de vlocidad fija
        """
        # Crear el vector de velocidad
        xd = [element * speed * MAX_SPEED / 100 for element in vector]
        # Inciar el movimiento
        self.rtde_c.speedL(xd, acc * MAX_ACC / 100, time)

    def speed_stop(self):
        """
        Detener movimiento de velocidad fija
        """
        self.rtde_c.speedStop()

    def servocontrol(self, coord_q):
        """
        Mueve el robot con servocontrol.

        Args:
            coord_q (array de floats): Coordenas a las que se debe mover el robot
        """
        # La UI de teclado envia comandos a unos 20 Hz; este tiempo mantiene servoL sincronizado con ese ciclo.
        self.rtde_c.servoL(coord_q, 0.5, 0.5, 0.05, 0.1, 500)

    def servocontrol_joint(self, coord_q):
        """
        Mueve el robot con servocontrol.

        Args:
            coord_q (array de floats): Coordenas a las que se debe mover el robot
        """
        # Coordenada la que moverse, velocidad y aceleración (no se usan), tiempo, lookahead y ganancia
        self.rtde_c.servoJ(coord_q, 0.5, 0.5, 0.002, 0.1, 500)

    def end_servocontrol(self):
        """termina el control de servo."""
        self.rtde_c.servoStop()

    def get_pos(self):
        """Devuelve las posición actual del robot."""
        return self.rtde_r.getActualTCPPose()

    def get_joints(self):
        """Devuelve las posición actual de las juntas del robot."""
        return self.rtde_r.getActualQ()

    def freedrive_on(self):
        """Activa el control manual."""
        self.rtde_c.freedriveMode(free_axes=[1, 1, 1, 0, 0, 0])

    def freedrive_off(self):
        """Desactiva el control manual."""
        self.rtde_c.endTeachMode()

    def get_aprox(self, pose):
        """
        Devuelve la coordenada de aproximación al punto.

        Args:
            pose (array de floats): Punto al que nos queremos aproximar
        """
        aprox = pose.copy()
        # Cogemos la coordenada z y le añadimos la tura de seguridad
        aprox[2] += self.alt_seg
        return aprox

    def get_pos_init(self):
        """Devuelve las posición incicial."""
        return self.pos_init

    def get_pos_ref(self):
        """Devuelve las posición de referencia."""
        return self.pos_ref

    def get_fuerzas(self):
        return self.rtde_r.getActualTCPForce()
