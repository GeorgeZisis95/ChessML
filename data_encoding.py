import numpy as np
import pickle
import tqdm
import os

from collections import defaultdict

def change_perspective(board:str) -> str:
    split_string = board.split()
    if split_string[1] == 'b':
        piece_position = split_string[0].split("/")
        split_string[0] = "/".join([char.swapcase() for char in reversed(piece_position)])
        split_string[1] = 'w'
        split_string[2] = "".join(sorted([char.swapcase() for char in split_string[2]]))
    return " ".join(split_string)

def helper_planes(board:str) -> np.ndarray:
    split_string = board.split()
    en_passant = np.zeros((8, 8), dtype=np.float32)
    alg_to_coord = lambda col, row: (8-int(row), ord(col)-ord('a')) 
    if split_string[3] != '-':
        col, row = split_string[3][0], split_string[3][1]
        the_rank, the_file = alg_to_coord(col, row)
        en_passant[the_rank][the_file] = 1
    fifty_move_count = np.full((8, 8), int(split_string[4]), dtype=np.float32)

    planes = [
        np.full((8, 8), int('K' in split_string[2]), dtype=np.float32),
        np.full((8, 8), int('Q' in split_string[2]), dtype=np.float32),
        np.full((8, 8), int('k' in split_string[2]), dtype=np.float32),
        np.full((8, 8), int('q' in split_string[2]), dtype=np.float32),
        fifty_move_count,
        en_passant,
    ]
    planes = np.asarray(planes, dtype=np.float32)
    assert planes.shape == (6,8,8), f"helper_planes shape is:{planes.shape} instead of (6,8,8)"
    return planes

def position_planes(board:str) -> np.ndarray:
    check_location = list(board.split()[0])

    for idx, char in enumerate(check_location):
        check_location[idx] = '1' * int(char) if char.isnumeric() else char
    check_location = "".join(check_location).replace("/","")

    pieces_order = 'KQRBNPkqrbnp'
    pieces_dict = {pieces_order[i]: i for i in range(12)}

    planes = np.zeros((12,8,8), dtype=np.float32)
    for row in range(8):
        for column in range(8):
            piece = check_location[row * 8 + column]
            if piece.isalpha():
                planes[pieces_dict[piece]][row][column] = 1

    assert planes.shape == (12,8,8), f"position_planes shape is: {planes.shape} instead of (12,8,8)"
    return planes

def get_canonical_board(board:str, perpective:bool=True) -> np.ndarray:
    if perpective:
        updated_board = change_perspective(board)
        return np.vstack((position_planes(updated_board), helper_planes(updated_board)))
    return np.vstack((position_planes(board), helper_planes(board)))


def create_uci_labels():
    labels_array = []
    letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    numbers = ['1', '2', '3', '4', '5', '6', '7', '8']
    promoted_to = ['q', 'r', 'b', 'n']

    for l1 in range(8):
        for n1 in range(8):
            destinations = [(t, n1) for t in range(8)] + \
                            [(l1, t) for t in range(8)] + \
                            [(l1 + t, n1 + t) for t in range(-7, 8)] + \
                            [(l1 + t, n1 - t) for t in range(-7, 8)] + \
                            [(l1 + a, n1 + b) for (a, b) in
                            [(-2, -1), (-1, -2), (-2, 1), (1, -2), (2, -1), (-1, 2), (2, 1), (1, 2)]]
            for (l2, n2) in destinations:
                if (l1, n1) != (l2, n2) and l2 in range(8) and n2 in range(8):
                    move = letters[l1] + numbers[n1] + letters[l2] + numbers[n2]
                    labels_array.append(move)
    for l1 in range(8):
        l = letters[l1]
        for p in promoted_to:
            labels_array.append(l + '2' + l + '1' + p)
            labels_array.append(l + '7' + l + '8' + p)
            if l1 > 0:
                l_l = letters[l1 - 1]
                labels_array.append(l + '2' + l_l + '1' + p)
                labels_array.append(l + '7' + l_l + '8' + p)
            if l1 < 7:
                l_r = letters[l1 + 1]
                labels_array.append(l + '2' + l_r + '1' + p)
                labels_array.append(l + '7' + l_r + '8' + p)
    return labels_array

def encode_data():
    total_states, total_actions, total_rewards = [], [], []
    files = os.listdir('expert_data_collection')
    for each_file in tqdm.tqdm(files):
        with open(f'expert_data_collection/{each_file}', 'rb') as f:
            experience_tuple = pickle.load(f)
        states, actions, reward = experience_tuple
        
        states = states[:,0]
        actions = actions[:,0]
        
        total_states.extend(states)
        total_actions.extend(actions)
        for _ in range(len(states)):
            total_rewards.append(reward)
    
    assert len(total_states) == len(total_actions) == len(total_rewards), f"Length of features and labels is not the same"

    occurences_dict = defaultdict(list)
    for i,item in enumerate(total_states):
        occurences_dict[item].append(i)
    occurences_dict = {k:v for k,v in occurences_dict.items() if len(v) >= 1}

    state_prob_dict = {}
    for current_state, indeces in occurences_dict.items():
        actions = [total_actions[i] for i in indeces]
        rewards = [total_rewards[i] for i in indeces]
        
        total_repetitions = len(indeces)
        correct_value = sum(rewards) / total_repetitions

        counts = {}
        for n in actions:
            counts[n] = counts.get(n, 0) + 1
        probs = np.zeros((len(create_uci_labels())))
        for action, count in counts.items():
            get_index = create_uci_labels().index(action)
            correct_probability = count / total_repetitions
            probs[get_index] = correct_probability
        state_prob_dict[current_state] = (probs, correct_value) 

    encoded_states, encoded_actions, encoded_values = [], [], []
    for state, action_value in state_prob_dict.items():
        action, value = action_value
        encoded_states.append(get_canonical_board(state))
        encoded_actions.append(action)
        encoded_values.append(value)

    if not os.path.isdir('encoded_data_collection'):
        os.mkdir('encoded_data_collection')
    np.save(f"encoded_data_collection/features", encoded_states)
    np.save(f"encoded_data_collection/labels", encoded_actions)
    np.save(f"encoded_data_collection/rewards", encoded_values)