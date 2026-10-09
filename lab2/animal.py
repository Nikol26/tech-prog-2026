from abc import abstractmethod
from pet import Pet


class Animal(Pet):

    def __init__(self, name, age):
        self.__name = name
        self.__age = age

    def happyBirthday(self):
        self.__age += 1

    def getName(self):
        return self.__name

    def getAge(self):
        return self.__age

    @abstractmethod
    def express(self):
        pass

    @abstractmethod
    def getAgeInHumanYears(self):
        pass