"""
The user class contains a GUID, their telegram id, and a list of workouts they created
"""


class User:
	def __init__(self, telegram_id="", first_name="", last_name=""):
		self.id = telegram_id
		self.first_name = first_name
		self.last_name = last_name
		self.saved_workouts = []
		self.completed_workouts = []
