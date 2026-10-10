from datetime import datetime
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
)

import qt_ui.uiconstants as CONST
from game import Game, persistency
from game.ato.flighttype import FlightType
from game.ato.flightstate import Uninitialized
from game.ato.package import Package
from game.ato.traveltime import TotEstimator
from game.profiling import logged_duration
from game.settings.settings import FastForwardStopCondition
from game.sim.missionstart import mission_start_time
from game.utils import meters
from qt_ui.models import GameModel
from qt_ui.simcontroller import SimController
from qt_ui.uiflags import UiFlags
from qt_ui.widgets.QBudgetBox import QBudgetBox
from qt_ui.widgets.QConditionsWidget import QConditionsWidget
from qt_ui.widgets.QFactionsInfos import QFactionsInfos
from qt_ui.widgets.QIntelBox import QIntelBox
from qt_ui.widgets.clientslots import MaxPlayerCount
from qt_ui.widgets.simspeedcontrols import SimSpeedControls
from qt_ui.windows.AirWingDialog import AirWingDialog
from qt_ui.windows.GameUpdateSignal import GameUpdateSignal
from qt_ui.windows.PendingTransfersDialog import PendingTransfersDialog
from qt_ui.windows.QWaitingForMissionResultWindow import QWaitingForMissionResultWindow


class QTopPanel(QFrame):
    def __init__(
        self, game_model: GameModel, sim_controller: SimController, ui_flags: UiFlags
    ) -> None:
        super(QTopPanel, self).__init__()
        self.game_model = game_model
        self.sim_controller = sim_controller
        self.dialog: Optional[QDialog] = None

        self.setMaximumHeight(70)

        self.conditionsWidget = QConditionsWidget(sim_controller)
        self.budgetBox = QBudgetBox(self.game)

        pass_turn_text = "Pass Turn"
        if not self.game or self.game.turn == 0:
            pass_turn_text = "Begin Campaign"
        # Exactly one control in this strip is the primary action, and it is the
        # one that generates and launches the mission. Everything else here —
        # Pass Turn, Air Wing, Transfers, Re-roll RED — is an ordinary button.
        # They all used to carry "btn-primary" too, which is why nothing in the
        # strip read as more important than anything else.
        self.passTurnButton = QPushButton(pass_turn_text)
        self.passTurnButton.setIcon(CONST.ICONS["PassTurn"])
        self.passTurnButton.clicked.connect(self.passTurn)
        if not self.game:
            self.passTurnButton.setEnabled(False)

        self.proceedButton = QPushButton("Take off")
        self.proceedButton.setIcon(CONST.ICONS["Proceed"])
        self.proceedButton.setProperty("style", "btn-primary")
        self.proceedButton.clicked.connect(self.launch_mission)
        if not self.game or self.game.turn == 0:
            self.proceedButton.setEnabled(False)

        self.factionsInfos = QFactionsInfos(self.game)

        self.air_wing = QPushButton("Air Wing")
        self.air_wing.setDisabled(True)
        self.air_wing.clicked.connect(self.open_air_wing)

        self.playable = QPushButton("My aircraft")
        self.playable.setDisabled(True)
        self.playable.setToolTip(
            "What you are flying this turn: saved points, loadout and data cartridge"
        )
        self.playable.clicked.connect(self.open_playable_aircraft)

        self.transfers = QPushButton("Transfers")
        self.transfers.setDisabled(True)
        self.transfers.clicked.connect(self.open_transfers)

        # Re-plan ONLY the enemy (RED) air tasking for the current turn, keeping the
        # player's (BLUE) hand-built frag untouched -- the coalition-selective form of
        # initialize_turn (the same path the engine uses on a red TGO buy/sell). Handy
        # after editing the enemy laydown so RED retasks onto it without discarding
        # your packages (unlike the conditions dialog's "Re-roll turn", which wipes
        # both sides).
        self.reroll_red_button = QPushButton("Re-roll RED")
        self.reroll_red_button.setDisabled(True)
        self.reroll_red_button.setToolTip(
            "Discard and re-plan the RED (enemy) air tasking for this turn while "
            "keeping your BLUE frag untouched. Does not change the clock or weather."
        )
        self.reroll_red_button.clicked.connect(self.reroll_red)

        self.intel_box = QIntelBox(self.game)

        self.buttonBox = QGroupBox("Misc")
        self.buttonBoxLayout = QHBoxLayout()
        self.buttonBoxLayout.addWidget(self.air_wing)
        self.buttonBoxLayout.addWidget(self.playable)
        self.buttonBoxLayout.addWidget(self.transfers)
        self.buttonBoxLayout.addWidget(self.reroll_red_button)
        self.buttonBox.setLayout(self.buttonBoxLayout)

        self.simSpeedControls = SimSpeedControls(sim_controller)

        self.proceedBox = QGroupBox("Proceed")
        self.proceedBoxLayout = QHBoxLayout()
        if ui_flags.show_sim_speed_controls:
            self.proceedBoxLayout.addLayout(self.simSpeedControls)
        self.proceedBoxLayout.addLayout(MaxPlayerCount(self.game_model.ato_model))
        self.proceedBoxLayout.addWidget(self.passTurnButton)
        self.proceedBoxLayout.addWidget(self.proceedButton)
        self.proceedBox.setLayout(self.proceedBoxLayout)

        self.controls = [
            self.air_wing,
            self.playable,
            self.transfers,
            self.reroll_red_button,
            self.simSpeedControls,
            self.passTurnButton,
            self.proceedButton,
        ]

        self.layout = QHBoxLayout()

        self.layout.addWidget(self.factionsInfos)
        self.layout.addWidget(self.conditionsWidget)
        self.layout.addWidget(self.budgetBox)
        self.layout.addWidget(self.intel_box)
        self.layout.addWidget(self.buttonBox)
        self.layout.addStretch(1)
        self.layout.addWidget(self.proceedBox)

        self.layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.layout)

        GameUpdateSignal.get_instance().gameupdated.connect(self.setGame)
        GameUpdateSignal.get_instance().budgetupdated.connect(self.budget_update)

    @property
    def game(self) -> Optional[Game]:
        return self.game_model.game

    def setGame(self, game: Optional[Game]):
        if game is None:
            return

        self.air_wing.setEnabled(True)
        self.playable.setEnabled(True)
        self.transfers.setEnabled(True)

        self.conditionsWidget.setCurrentTurn(game.turn, game.conditions)

        if game.conditions.weather.clouds:
            base_m = game.conditions.weather.clouds.base
            base_ft = int(meters(base_m).feet)
            self.conditionsWidget.setToolTip(f"Cloud Base: {base_m}m / {base_ft}ft")
        else:
            self.conditionsWidget.setToolTip("")

        self.intel_box.set_game(game)
        self.budgetBox.setGame(game)
        self.factionsInfos.setGame(game)

        self.setControls(True)

        if game.turn > 0:
            self.passTurnButton.setText("Pass Turn")
        elif game.turn == 0:
            self.passTurnButton.setText("Begin Campaign")
            self.proceedButton.setEnabled(False)
            self.simSpeedControls.setEnabled(False)
            # No turn to re-plan before the campaign starts.
            self.reroll_red_button.setEnabled(False)
        else:
            raise RuntimeError(f"game.turn out of bounds!\n  value = {game.turn}")

    def open_air_wing(self):
        self.dialog = AirWingDialog(self.game_model, self.window())
        self.dialog.show()

    def open_playable_aircraft(self) -> None:
        from qt_ui.windows.playable import PlayableAircraftDialog

        self.playable_dialog = PlayableAircraftDialog(self.game_model, self.window())
        self.playable_dialog.show()

    def open_transfers(self):
        self.dialog = PendingTransfersDialog(self.game_model)
        self.dialog.show()

    def reroll_red(self):
        """Re-plan RED's ATO for the current turn, keeping BLUE's frag untouched.

        Uses the coalition-selective ``Game.initialize_turn(for_red=True,
        for_blue=False)`` -- the same path the engine takes on a red TGO buy/sell -- so
        the player's hand-built BLUE packages, rosters, loadouts and TOTs are left
        exactly as they were while RED replans against the current laydown. The clock
        and weather are not touched.
        """
        from game.server import EventStream
        from game.sim.gameupdateevents import GameUpdateEvents

        game = self.game
        if game is None or game.turn <= 0:
            return

        confirm = QMessageBox.question(
            self,
            "Re-roll RED plan?",
            (
                "This discards RED's current flight plans and re-plans them for the "
                "current laydown.<br /><br />"
                "Your BLUE frag is kept untouched. Continue?"
            ),
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        with logged_duration("Re-rolling RED plan"):
            events = GameUpdateEvents()
            game.initialize_turn(events, for_red=True, for_blue=False)
            EventStream.put_nowait(events)
            GameUpdateSignal.get_instance().updateGame(game)
            state = game.check_win_loss()
            GameUpdateSignal.get_instance().gameStateChanged(state)

    def passTurn(self):
        with logged_duration("Skipping turn"):
            self.game.pass_turn(no_action=True)
            GameUpdateSignal.get_instance().updateGame(self.game)
            state = self.game_model.game.check_win_loss()
            GameUpdateSignal.get_instance().gameStateChanged(state)
            self.proceedButton.setEnabled(True)

    # Defensive air patrols are meant to be on-station at mission start, so a
    # cold-start spin-up that begins before mission start is expected, not a
    # misplan: the flight spawns cold at mission start and its on-station time
    # simply slips a little (there is no package rendezvous to miss). Worse, the
    # auto-scheduler reserves only the 2-minute AI startup when timing CAP, while a
    # player-flown flight gets the much larger "player startup allowance" -- so a
    # player-occupied cold-start BARCAP would otherwise trip this warning every
    # single turn. For CAP we therefore check the takeoff time (which ignores the
    # ground spin-up) instead of the startup time, so a genuine "can't even take
    # off in time" misplan still warns while the normal cold-start CAP does not.
    _DCA_TYPES = {FlightType.BARCAP, FlightType.TARCAP}

    def negative_start_packages(self, now: datetime) -> List[Package]:
        packages = []
        for package in self.game_model.ato_model.ato.packages:
            if not package.flights:
                continue
            is_dca = package.primary_task in self._DCA_TYPES
            for flight in package.flights:
                if isinstance(flight.state, Uninitialized):
                    flight.state.reinitialize(now)
                if flight.state.is_waiting_for_start:
                    start = (
                        flight.flight_plan.takeoff_time()
                        if is_dca
                        else flight.flight_plan.startup_time()
                    )
                    if start < now:
                        packages.append(package)
                        break
        return packages

    @staticmethod
    def fix_tots(packages: List[Package], now: datetime) -> None:
        for package in packages:
            estimator = TotEstimator(package)
            package.time_over_target = estimator.earliest_tot(now)

    def confirm_no_client_launch(self) -> bool:
        result = QMessageBox.question(
            self,
            "Continue without player pilots?",
            (
                "No player pilots have been assigned to flights. Continuing will allow "
                "the AI to perform the mission, but players will be unable to "
                "participate.<br />"
                "<br />"
                "To assign player pilots to a flight, select a package from the "
                "Packages panel on the left of the main window, and then a flight from "
                "the Flights panel below the Packages panel. The edit button below the "
                "Flights panel will allow you to assign specific pilots to the flight. "
                "If you have no player pilots available, the checkbox next to the "
                "name will convert them to a player.<br />"
                "<br />Click 'Yes' to continue with an AI only mission"
                "<br />Click 'No' if you'd like to make more changes."
            ),
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return result == QMessageBox.StandardButton.Yes

    def confirm_negative_start_time(
        self, negative_starts: List[Package], now: datetime
    ) -> bool:
        formatted = "<br />".join(
            [f"{p.primary_task} {p.target.name}" for p in negative_starts]
        )
        mbox = QMessageBox(
            QMessageBox.Icon.Question,
            "Continue with past start times?",
            (
                "Some flights in the following packages have start times set "
                "earlier than mission start time:<br />"
                "<br />"
                f"{formatted}<br />"
                "<br />"
                "Flight start times are estimated based on the package TOT, so it "
                "is possible that not all flights will be able to reach the "
                "target area at their assigned times.<br />"
                "<br />"
                "You can either continue with the mission as planned, with the "
                "misplanned flights potentially flying too fast and/or missing "
                "their rendezvous; automatically fix negative TOTs; or cancel "
                "mission start and fix the packages manually."
            ),
            parent=self,
        )
        auto = mbox.addButton(
            "Fix TOTs automatically", QMessageBox.ButtonRole.ActionRole
        )
        ignore = mbox.addButton(
            "Continue without fixing", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel = mbox.addButton(QMessageBox.StandardButton.Cancel)
        mbox.setEscapeButton(cancel)
        mbox.exec_()
        clicked = mbox.clickedButton()
        if clicked == auto:
            self.fix_tots(negative_starts, now)
            return True
        elif clicked == ignore:
            return True
        return False

    def check_no_missing_pilots(self) -> bool:
        missing_pilots = []
        for package in self.game.blue.ato.packages:
            for flight in package.flights:
                if flight.missing_pilots > 0:
                    missing_pilots.append((package, flight))

        if not missing_pilots:
            return False

        formatted = "<br />".join(
            [f"{p.primary_task} {p.target.name}: {f}" for p, f in missing_pilots]
        )
        mbox = QMessageBox(
            QMessageBox.Icon.Critical,
            "Flights are missing pilots",
            (
                "The following flights are missing one or more pilots:<br />"
                "<br />"
                f"{formatted}<br />"
                "<br />"
                "You must either assign pilots to those flights or cancel those "
                "missions."
            ),
            parent=self,
        )
        mbox.setEscapeButton(mbox.addButton(QMessageBox.StandardButton.Close))
        mbox.exec_()
        return True

    def launch_mission(self):
        """Finishes planning and waits for mission completion."""
        if not self.game.ato_has_clients() and not self.confirm_no_client_launch():
            return

        if self.check_no_missing_pilots():
            return

        from game.agent.service import run_fallback_if_needed

        if run_fallback_if_needed(self.game):
            self.game.message(
                "Red planned by the game",
                "Red had no missions at Take Off, so the game's own planner planned them.",
            )

        if self.sim_controller.started:
            now = self.sim_controller.current_time_in_sim
        else:
            # The mission begins up to 30 min early so ground starts fit (§104).
            now = mission_start_time(self.game)
        negative_starts = self.negative_start_packages(now)
        if negative_starts:
            if not self.confirm_negative_start_time(negative_starts, now):
                return

        if self.game.settings.fast_forward_stop_condition not in [
            FastForwardStopCondition.DISABLED,
            FastForwardStopCondition.MANUAL,
        ]:
            with logged_duration("Simulating to first contact"):
                self.sim_controller.run_to_first_contact()
        self.sim_controller.generate_miz(
            persistency.mission_path_for("retribution_nextturn.miz")
        )

        waiting = QWaitingForMissionResultWindow(self.game, self.sim_controller, self)
        waiting.exec_()

    def budget_update(self, game: Game):
        self.budgetBox.setGame(game)

    def setControls(self, enabled: bool):
        for controller in self.controls:
            controller.setEnabled(enabled)

    def check_for_contact(self) -> bool:
        if (
            len(self.game.blue.ato.packages) == 0
            and len(self.game.red.ato.packages) == 0
        ):
            mbox = QMessageBox(
                QMessageBox.Icon.Critical,
                "No flights planned",
                (
                    "No flights are planned and fast forward to first contact "
                    "is enabled. You must either plan flights or disable fast forward."
                ),
                parent=self,
            )
            mbox.setEscapeButton(mbox.addButton(QMessageBox.StandardButton.Close))
            mbox.exec_()
            return False
        return True
