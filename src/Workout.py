"""
The workout class contains meta information about a particular workout 
(such as the workout creator, average length, difficulty level)
as well as a list of exercises.
"""

class Workout:
	def __init__(self, created_by, length=0, difficulty="easy"):
		self.created_by = created_by
		self.length = length
		self.difficulty = difficulty
		self.running = False
		self.saves = 0