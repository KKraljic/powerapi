# Copyright (C) 2018  University of Lille
# Copyright (C) 2018  INRIA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from smartwatts.handler import InitHandler, Handler
from smartwatts.report import PowerReport
from smartwatts.message import ErrorMessage
from smartwatts.message import OKMessage, StartMessage
from smartwatts.database import DBError


class StartHandler(Handler):
    """
    Handle Start Message
    """

    def handle(self, msg, state):
        """
        Initialize the output database

        :param smartwatts.StartMessage msg: Message that initialize the actor.
        :param smartwatts.State state: State of the actor.
        """

        # If it's already initialized, return state
        if state.initialized:
            return state

        # If it's not a StartMessage, return state
        if not isinstance(msg, StartMessage):
            return state

        # If load database fail, return state
        try:
            state.database.load()
        except DBError as error:
            state.socket_interface.send_control(ErrorMessage(error.msg))
            return state

        # Else, we can initialize state
        state.initialized = True
        state.socket_interface.send_control(OKMessage())
        return state


class PowerHandler(InitHandler):
    """
    Allow to save the PowerReport received.
    """

    def handle(self, msg, state):
        """
        Save the msg in the database

        :param smartwatts.PowerReport msg: PowerReport to save.
        :param smartwatts.State state: State of the actor.
        """
        if not isinstance(msg, PowerReport):
            return state

        state.database.save(msg.serialize())
        return state


class TimeoutHandler(InitHandler):
    """
    Pusher timeout kill the actor
    """

    def handle(self, msg, state):
        """
        Kill the actor by setting alive to False

        :param None msg: None.
        :param smartwatts.State state: State of the actor.
        """
        state.alive = False
        return state