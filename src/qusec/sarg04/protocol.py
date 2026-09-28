import random

def generate_sarg04_candidate(input_bit: int, basis: str) -> tuple:
    """
    Candidate sets:
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

def sift_sarg04(bob_res: int, bob_basis: str, candidate_set: tuple) -> dict:
    """
    SARG04 sifting logic. Bob eliminates the candidate orthogonal to his result.
    """
    ruled_out = None
    if bob_basis == 'Z':
        if bob_res == 0:
            ruled_out = (1, 'Z')
        else:
            ruled_out = (0, 'Z')
    else: # X
        if bob_res == 0:
            ruled_out = (1, 'X')
        else:
            ruled_out = (0, 'X')

    conclusive = False
    reconstructed_bit = None
    
    if ruled_out in candidate_set:
        conclusive = True
        # The other one is the bit
        for cand in candidate_set:
            if cand != ruled_out:
                reconstructed_bit = cand[0]
                break

    return {
        "conclusive": conclusive,
        "reconstructed_bit": reconstructed_bit,
        "ruled_out": ruled_out
    }

def get_decoy_state(mu_prob, nu_prob, vac_prob):
    r = random.random()
    if r < mu_prob:
        return 'mu'
    elif r < mu_prob + nu_prob:
        return 'nu'
    return 'vac'
