import random

def generate_sarg04_candidate(input_bit: int, basis: str) -> tuple:
    """
    Candidate sets (Paper Section III-H):
    Alice announces a pair of non-orthogonal states from {|0>, |1>, |+>, |->}, one of which was sent.
    A: {(0,Z), (0,X)}
    B: {(0,Z), (1,X)}
    C: {(1,Z), (0,X)}
    D: {(1,Z), (1,X)}
    """
    if input_bit == 0 and basis == 'Z':
        return random.choice([((0,'Z'), (0,'X')), ((0,'Z'), (1,'X'))])
    elif input_bit == 0 and basis == 'X':
        return random.choice([((0,'Z'), (0,'X')), ((1,'Z'), (0,'X'))])
    elif input_bit == 1 and basis == 'Z':
        return random.choice([((1,'Z'), (0,'X')), ((1,'Z'), (1,'X'))])
    elif input_bit == 1 and basis == 'X':
        return random.choice([((0,'Z'), (1,'X')), ((1,'Z'), (1,'X'))])
    return ((0,'Z'), (0,'X'))

def sift_sarg04(bob_res: int, bob_basis: str, candidate_set: tuple, sent_state: tuple = None) -> dict:
    """
    SARG04 sifting logic (Paper Section III-H):
    Bob can identify the sent state only when his outcome is orthogonal to one of the two
    announced candidates, which occurs with probability 1/4 per qubit.
    If the ruled-out state was Alice's true sent state (due to noise or attack), an error is detected.
    """
    ruled_out = None
    if bob_basis == 'Z':
        if bob_res == 0:
            ruled_out = (1, 'Z')
        else:
            ruled_out = (0, 'Z')
    else:  # X
        if bob_res == 0:
            ruled_out = (1, 'X')
        else:
            ruled_out = (0, 'X')

    conclusive = False
    reconstructed_state = None
    reconstructed_bit = None
    is_error = False

    if ruled_out in candidate_set:
        conclusive = True
        # Bob eliminates the candidate orthogonal to his result
        for cand in candidate_set:
            if cand != ruled_out:
                reconstructed_state = cand
                break

        if sent_state is not None:
            if reconstructed_state == sent_state:
                reconstructed_bit = sent_state[0]
                is_error = False
            else:
                reconstructed_bit = 1 - sent_state[0]
                is_error = True
        else:
            reconstructed_bit = reconstructed_state[0] if reconstructed_state is not None else None

    return {
        "conclusive": conclusive,
        "reconstructed_bit": reconstructed_bit,
        "reconstructed_state": reconstructed_state,
        "ruled_out": ruled_out,
        "is_error": is_error,
    }

def get_decoy_state(mu_prob: float = 0.6, nu_prob: float = 0.3, vac_prob: float = 0.1) -> str:
    """
    Decoy state selection (Paper Section II, VI-D):
    mu: signal state
    nu: weak decoy state
    vac: vacuum state
    """
    r = random.random()
    if r < mu_prob:
        return 'mu'
    elif r < mu_prob + nu_prob:
        return 'nu'
    return 'vac'
