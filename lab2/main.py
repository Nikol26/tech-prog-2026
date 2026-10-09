from parrot import Parrot
from turtle import Turtle
from person import Person


kesha = Parrot("Kesha", 2)
zavala = Turtle("Zavala", 4)

kesha.happyBirthday()

jack = Person("Jack", kesha)
john = Person("John")

jack.getPetInfo()
john.getPetInfo()

john.setPet(zavala)
john.getPetInfo()