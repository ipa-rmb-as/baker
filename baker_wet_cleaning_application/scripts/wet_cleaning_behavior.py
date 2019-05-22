#!/usr/bin/env python

import threading

import behavior_container
import trolley_movement_behavior
import tool_changing_behavior
import room_wet_floor_cleaning_behavior


class WetCleaningBehavior(behavior_container.BehaviorContainer):

	#========================================================================
	# Description:
	# Handles the wet cleaning process (i.e. Floor cleaning, Trashcan)
	# for all rooms provided in a given list
	#========================================================================

	# Method for setting parameters for the behavior
	def setParameters(self, database_handler, room_information_in_meter, sequence_data, mapping, robot_frame_id,
					  robot_radius, coverage_radius, field_of_view, field_of_view_origin, use_cleaning_device):
		# Parameters set from the outside
		self.database_handler_= database_handler
		self.room_information_in_meter_ = room_information_in_meter
		self.sequence_data_ = sequence_data
		self.mapping_ = mapping
		self.robot_frame_id_ = robot_frame_id
		self.robot_radius_ = robot_radius
		self.coverage_radius_ = coverage_radius
		self.field_of_view_ = field_of_view
		self.field_of_view_origin_ = field_of_view_origin
		self.use_cleaning_device_ = use_cleaning_device	# todo: hack: cleaning device can be turned off for trade fair show


	# Method for returning to the standard pose of the robot
	def returnToRobotStandardState(self):
		# nothing to save
		# nothing to be undone
		pass

	# Driving through room and wet cleaning
	def driveCleaningTrajectory(self, room_counter, current_room_index):

		self.printMsg("Moving to next room with current_room_index = " + str(current_room_index))

		# Interruption opportunity
		if self.handleInterrupt() >= 1:
			return

		self.room_wet_floor_cleaner_.setParameters(
			room_map_data=self.database_handler_.database_.getRoom(self.mapping_.get(current_room_index)).room_map_data_,
			room_center=self.room_information_in_meter_[current_room_index].room_center,
			map_data=self.database_handler_.database_.global_map_data_.map_image_,
			map_resolution=self.database_handler_.database_.global_map_data_.map_resolution_,
			map_origin=self.database_handler_.database_.global_map_data_.map_origin_,
			map_header_frame_id=self.database_handler_.database_.global_map_data_.map_header_frame_id_,
			robot_frame_id=self.robot_frame_id_,
			robot_radius=self.robot_radius_,
			coverage_radius=self.coverage_radius_,
			field_of_view=self.field_of_view_,
			field_of_view_origin=self.field_of_view_origin_,
			use_cleaning_device=self.use_cleaning_device_	# todo: hack: cleaning device can be turned off for trade fair show
		)
		self.room_wet_floor_cleaner_.executeBehavior()

		# Interruption opportunity
		if self.handleInterrupt() >= 1:
			return

		# Mark the current room as finished
		self.printMsg("ID of cleaned room: " + str(self.mapping_.get(room_counter)))
		self.database_handler_.checkoutCompletedRoom(self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)), 1)
		self.printMsg(str(self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)).open_cleaning_tasks_))

		# Interruption opportunity
		if self.handleInterrupt() >= 1:
			return

		# Adding log entry for wet cleaning
		self.database_handler_.addLogEntry(
			self.mapping_.get(room_counter), # room id
			1, # status (1=Completed)
			1, # cleaning task (1=wet only)
			0, # (found dirtspots)
			0, # trashcan count
			0, # surface area
			[], # room issues
			0, # water amount
			0 # battery usage
		)

	# Searching for trashcans
	def trashcanRoutine(self, room_counter):
		# ==========================================
		# insert trashcan handling here
		# ==========================================
		self.database_handler_.checkoutCompletedRoom(self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)), -1)

		# Adding log entry for trashcan emptying
		self.database_handler_.addLogEntry(
			self.mapping_.get(room_counter), # room id
			1, # status (1=Completed)
			-1, # cleaning task (-1=trashcan only)
			0, # (found dirtspots)
			0, # trashcan count
			0, # surface area
			[], # room issues
			0, # water amount
			0 # battery usage
		)

	# Implemented Behavior
	def executeCustomBehavior(self):
		self.trolley_mover_ = trolley_movement_behavior.TrolleyMovementBehavior("TrolleyMovementBehavior", self.interrupt_var_)
		self.tool_changer_ = tool_changing_behavior.ToolChangingBehavior("ToolChangingBehavior", self.interrupt_var_)
		self.room_wet_floor_cleaner_ = room_wet_floor_cleaning_behavior.RoomWetFloorCleaningBehavior("RoomWetFloorCleaningBehavior", self.interrupt_var_)

		# Tool changing
		self.tool_changer_.setParameters(self.database_handler_)
		self.tool_changer_.executeBehavior()

		# Room counter index: Needed for mapping of room_indices <--> RoomItem.room_id
		room_counter = 0

		# todo: tsp on the checkpoints / rooms ?
		for current_checkpoint_index in range(len(self.sequence_data_.checkpoints)):

			# Trolley movement to checkpoint
			self.trolley_mover_.setParameters(self.database_handler_)
			self.trolley_mover_.executeBehavior()

			for current_room_index in self.sequence_data_.checkpoints[current_checkpoint_index].room_indices:

				# Handling of selected room
				cleaning_thread = threading.Thread(target = self.driveCleaningTrajectory(room_counter, current_room_index))
				cleaning_thread.start()
				cleaning_tasks = self.database_handler_.database_.getRoom(self.mapping_.get(room_counter)).open_cleaning_tasks_
				if -1 in cleaning_tasks: # todo (rmb-ma): what is this? Is it useful?
					trashcan_thread = threading.Thread(target = self.trashcanRoutine(room_counter))
					trashcan_thread.start()
				cleaning_thread.join() # todo (rmb-ma) ???
				
				# Increment the current room counter index
				room_counter = room_counter + 1