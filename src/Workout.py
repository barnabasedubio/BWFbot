"""
The workout class contains meta information about a particular workout 
(such as the workout creator, average length, difficulty level)
as well as a list of exercises.
"""

class Workout:
	def __init__(self, id, created_by=USER, length=0, difficulty="easy"):
		self.id = 0 # TODO
		self.created_by = created_by
		self.length = length
		self.difficulty = difficulty
		self.running = False

	def start():
		self.running = True

	def pause():
		self.running = False