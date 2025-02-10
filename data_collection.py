from stockfish import Stockfish

stockfish = Stockfish(path="/usr/games/stockfish")

import numpy as np
import random
import chess
import glob
import os

def check_finish(board) -> bool:
    if any([board.is_checkmate(),
            board.is_stalemate(),
            board.outcome(),
            board.can_claim_draw(),
            board.can_claim_threefold_repetition(),
            board.can_claim_fifty_moves(),
            board.is_insufficient_material(),
            board.is_fivefold_repetition(),
            board.is_seventyfive_moves(),
            ]):
        return True
    return False

def get_game_id() -> int:
    files = (glob.glob(r'expert_data_collection/*.npy'))
    if len(files) == 0:
        return 1
    highest_index = 0
    for f in files:
        current_index = int(f.split("actions_and_states_game_")[-1].split(".npy")[0])
        highest_index = max(highest_index, current_index)

    return highest_index + 1

def save_data(total_actions:list, total_states:list):
    total_actions = np.array(total_actions).reshape(-1, 1)
    total_states = np.array(total_states).reshape(-1,1)
    actions_and_states = np.concatenate((total_actions, total_states), axis = 1)
    game_id = get_game_id()
    if not os.path.isdir('expert_data_collection'):
        os.mkdir('expert_data_collection')
    np.save(f"expert_data_collection/actions_and_states_game_{game_id}.npy", actions_and_states)
    print("Expert Data Collected Succesfully.")

def get_board(time_step:int, game_id:int=1) -> object:
    data = np.load(f"expert_data_collection/actions_and_states_game_{game_id}.npy")
    actions = data[:, 0]

    assert time_step <= len(actions), 'Time step exceeds maximum episode length'

    test_board = chess.Board()
    for i in range(time_step):
        action = actions[i]
        test_board.push_san(action)
    return test_board

def generate_games(_):
    stockfish.set_elo_rating(elo_rating=1350)

    weight_cases = {
        1: [100],
        2: [80, 20],
        3: [80, 15, 5]
    }
    max_actions = 100

    action_list, state_list = [], []

    board = chess.Board()
    stockfish.set_position([])

    while True:
        best_actions = stockfish.get_top_moves(3)
        weights = weight_cases.get(len(best_actions), [])
        action_taken = random.choices(best_actions, weights=weights, k=1)[0]["Move"]

        state_list.append(stockfish.get_fen_position())
        action_list.append(action_taken)

        board.push_san(action_taken)
        stockfish.set_position(action_list)

        if check_finish(board) or len(action_list) > max_actions:
            break

    save_data(action_list, state_list)