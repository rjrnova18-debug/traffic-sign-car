# Original motor test that ran on the Raspberry Pi (May 2025).
# The file itself was lost; it was transcribed line by line from photos of the
# Pi's screen. It is the only surviving piece of the car's code, and it is where
# the pin numbers in src/signcar/config.py come from.
import RPi.GPIO as GPIO
import time

#Define Pins
IN1 = 17
IN2 = 18
#ENA = 22
IN3 = 23
IN4 = 24
#ENB = 25

# Config pins as output
GPIO.setmode(GPIO.BCM)
GPIO.setup([IN1, IN2, IN3, IN4], GPIO.OUT)

# Set PWM signal
#PWM_A = GPIO.PWM(ENA, 100)
#PWM_A.start(0)
#PWM_B = GPIO.PWM(ENB, 100)
#PWM_B.start(0)



def forward():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    #PWM_A.ChangeDutyCycle(70)

    GPIO.output(IN4, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    #PWM_B.ChangeDutyCycle(70)

def backward():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    #PWM_A.ChangeDutyCycle(70)

    GPIO.output(IN4, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    #PWM_B.ChangeDutyCycle(70)

def right ():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    #PWM_A.ChangeDutyCycle(70)

    GPIO.output(IN4, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    #PWM_B.ChangeDutyCycle(70)


def left ():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    #PWM_A.ChangeDutyCycle(70)

    GPIO.output(IN4, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    #PWM_B.ChangeDutyCycle(70)


def stop():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    #PWM_A.ChangeDutyCycle(0)

    GPIO.output(IN4, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    #PWM_B.ChangeDutyCycle(0)

try:
    while True:
        cmd = input("Command (w = forward, s = backward/nd = right, a = left /n e = stop): ")
        if cmd == "w":
            forward()

        elif cmd == "s":
            backward()

        elif cmd == "d":
            right()
            time.sleep(1)
            stop()

        elif cmd == "a":
            left()
            time.sleep(1)
            stop()

        elif cmd == "e":
            stop()

        elif cmd =="x":
            break
        else:
            print("Unknown command")
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
