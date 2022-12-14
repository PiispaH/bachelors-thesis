import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as ani
import timeit
import networkx as nx
from random import randint
from json import load
from matplotlib.animation import PillowWriter
#import matplotlib;matplotlib.use("TkAgg")

# Reading the config file and setting the constants values
with open("config.json") as file:
    constants = load(file)

N = constants["N"]                                      # Number of oscillators
T = constants["T"]                                      # Temperature
r = constants["r"]                                      # Radius of the initial state
phi = constants["phi"]                                  # Rotation of the initial state
INITIAL_Q = constants["INITIAL_Q"]                      # Value of Q the initial state
INITIAL_P = constants["INITIAL_P"]                      # Value of P in the initial state

MIN_X_AND_Y = constants["MIN_X_AND_Y"]                  # Minimum value for x and y in plots
MAX_X_AND_Y = constants["MAX_X_AND_Y"]                  # Maximum value for x and y in plots
RESOLUTION = constants["RESOLUTION"]                    # Resolution of the plots
DURATION = constants["DURATION"]                        # The duration of the simulation
TIME_STEP = constants["TIME_STEP"]                      # Time step of simulation
SAVE = constants["SAVE"]                                # Whether to save the animations and plots or not
STEPS = int(DURATION / TIME_STEP)                       # How many steps in whole simulation
TIMES = np.linspace(0, STEPS, STEPS + 1) * TIME_STEP    # Instances of time, where values are calculated

# The frequencies of the oscillators
frequencies = np.ones(N)
#frequencies = np.array([1.1, 1.0, 1.0, 1.0])

# Vector for the initial state
initial_state_vector = np.array([INITIAL_Q, INITIAL_P])

# Defining a NxN zero matrix to help construct the other matrices
zero_block = np.zeros((N, N))

# Defining the J matrix
J = np.block([[zero_block, np.identity(N)],
              [-1 * np.identity(N), zero_block]])


# Calculates the expectation value of the operators Q_i squared
def expectation_value_Q2(frequency: np.ndarray) -> np.ndarray:
    """
        Args: frequency: List of the oscillators frequencies

        Return: array of
    """

    if T == 0:
        values = 0.5 / frequency

    else:
        values = (1 / (np.exp(frequency / T) - 1) + 0.5) / frequency

    return values


# Calculates the expectation value of the operators P_i squared
def expectation_value_P2(frequency: np.ndarray) -> np.ndarray:
    if T == 0:
        value = 0.5 * frequency

    else:
        value = (1 / (np.exp(frequency / T) - 1) + 0.5) * frequency

    return value


def initial_cov_matrix(zero: np.ndarray, oscillator_freqs: np.ndarray,
                       Q2_expectation: np.ndarray, P2_expectation: np.ndarray) -> np.ndarray:
    # If only one oscillator is simulated, squeezing and rotation of the state are taken into account
    if N == 1:
        # Creating the parts presenting the squeezing and displacement operators in the covariance matrix
        Q2_multiplier = np.cosh(2 * r) + np.sinh(2 * r) * np.cos(phi)
        P2_multiplier = np.cosh(2 * r) - np.sinh(2 * r) * np.cos(phi)

        # The off diagonal components of the matrix
        off_diagonal = - (1 / (np.exp(oscillator_freqs / T) - 1) + 0.5) * np.sinh(2 * r) * np.sin(phi)

        # Creating the covariance matrix describing the initial state
        cov_X_initial = np.block([[np.diag(Q2_expectation * Q2_multiplier), off_diagonal],
                                  [off_diagonal, np.diag(P2_expectation * P2_multiplier)]])

    # If more than one oscillator is simulated, the initial covariance matrix is a diagonal matrix
    # consisting of the Q2 and P2 expectation values
    else:
        cov_X_initial = np.block([[np.diag(Q2_expectation), zero],
                                  [zero, np.diag(P2_expectation)]])

    return cov_X_initial


def new_cov_calculation(S: np.ndarray, cov_X: np.ndarray) -> tuple:
    new_cov_X = S @ cov_X @ S.transpose()
    diagonal = np.diagonal(new_cov_X)
    return diagonal, new_cov_X


def covariance_save(t: float, oscillators: dict, diagonal_non: np.ndarray,
                    diagonal_int: np.ndarray, diagonal_old: np.ndarray):

    for i in range(N):
        if t == 0:
            oscillators[f"{i}"] = {'Q': [(diagonal_non[i], diagonal_int[i], diagonal_old[i])]
                                   , 'P': [(diagonal_non[i + N], diagonal_int[i + N], diagonal_old[i + N])]}

        else:
            oscillators[f"{i}"]['Q'].append((diagonal_non[i], diagonal_int[i], diagonal_old[i]))
            oscillators[f"{i}"]['P'].append((diagonal_non[i + N], diagonal_int[i + N], diagonal_old[i + N]))


# Applies the cos(??t) operation on each frequency
def cosine(frequency: np.ndarray, t: float) -> np.ndarray:
    return np.cos(frequency * t)


# Vectorizes the function for convenience
cosine_vector = np.vectorize(cosine)


# Applies the sin(??t) operation on each frequency
def sine(frequency: np.ndarray, t: float) -> np.ndarray:
    return np.sin(frequency * t)


sine_vector = np.vectorize(sine)


def matrix_A(graph, oscillator_frequencies: np.ndarray) -> np.ndarray:
    laplacian = nx.laplacian_matrix(graph).toarray()
    freq = np.diag(oscillator_frequencies) ** 2

    return freq * 0.5 + laplacian * 0.5


# Creates the network
def network(plot=False):
    # The graph containing N quantum mechanical harmonic oscillators
    if N == 1:
        G = nx.newman_watts_strogatz_graph(N, 1, 0.5)
    else:
        G = nx.newman_watts_strogatz_graph(N, 2, 0.2)

    # Adding random weights
    for u, v in G.edges():
        G.edges[u, v]['weight'] = randint(1, 5)

    # Construction of matrix A
    A = matrix_A(G, frequencies)

    # Draws the network
    if plot and N > 1:
        nx.draw_circular(G)

    eigenvalues, K = np.linalg.eigh(A)
    print(f"Diagonalized properly: {sanity_check_2(eigenvalues, K, A)}")

    return G, A, eigenvalues, K


# Creates the symplectic matrix for a specific moment in time
def symplectic(t: float, K: np.ndarray, kind: str) -> np.ndarray:
    block_cos = np.diag(cosine_vector(frequencies, t))
    block_sin = np.diag(sine_vector(frequencies, t))

    freq_diag = np.diag(frequencies)
    inverse_freq_diag = np.linalg.inv(freq_diag)

    if kind == "interacting":
        S = np.block([[K @ block_cos, K @ (inverse_freq_diag * block_sin)],
                      [K @ (-freq_diag * block_sin), K @ block_cos]])
    elif kind == "non_interacting":
        S = np.block([[block_cos, inverse_freq_diag * block_sin],
                      [-freq_diag * block_sin, block_cos]])
    else:
        raise ValueError("Function symplectic() argument 'kind' invalid")

    return S


# Checks whether the symplectic matrix is really symplectic
def sanity_check_1(S1: np.ndarray, S2: np.ndarray, S3: np.ndarray) -> bool:
    S_list = [S1, S2, S3]
    for S in S_list:
        new_J_matrix = S @ J @ np.transpose(S)
        if not np.allclose(J, new_J_matrix):
            return False

    return True


# Checks if the Hamiltonian has been diagonalized properly
def sanity_check_2(eigenvalues, K: np.ndarray, A: np.ndarray) -> bool:
    a = np.diag(eigenvalues)
    return np.allclose(a, K.transpose() @ A @ K)


# Definition of the Wigner function for one oscillator
def wigner_function(cov, vector, state_vector) -> np.ndarray:
    oe = vector - state_vector
    wigner = 1 / (2 * np.pi * np.sqrt(np.linalg.det(cov))) *\
        np.exp(-0.5 * oe @ np.linalg.inv(cov) @ oe.transpose())

    return wigner


np.vectorize(wigner_function)


def wigner_operations(grid: np.ndarray, cov_X: np.ndarray, storage: list, state_vector: np.ndarray):
    current_wigner_values = []

    # Iterates through the grid that the Wigner function will be calculated in row by row
    for row in grid:
        wig_row = []

        # Calculates the value of the Wigner function for every x and y coordinate pair in this row
        for i in range(RESOLUTION):
            wigner_value = wigner_function(cov_X, row[i], state_vector)
            wig_row.append(wigner_value)

        # The list containing all the Wigner function values for the specific row is added to a list
        # that contains every rows wigner function values
        current_wigner_values.append(np.array(wig_row))

    # The list containing all calculated Wigner function values for this instance in time is added to storage
    storage.append(np.array(current_wigner_values))


# Visualizes the distribution of the Wigner function in a 2D contour plot
def wigner_visualization(W, ax_range):
    fig = plt.figure()
    ax = plt.axes(xlabel="Q", ylabel="P")

    plt.contourf(ax_range, ax_range, W, 100)
    plt.colorbar()

    fig.suptitle("Wigner function")

    plt.show()


# Draws the frames for animating the Wigner function
def draw_frame(frame, W, ax_range) -> plt.Figure:
    cont = plt.contourf(ax_range, ax_range, W[frame])
    return cont


# Runs animation
def wigner_animation(W, ax_range, fig, save=False):
    anim = ani.FuncAnimation(fig, draw_frame, frames=len(W), fargs=(W, ax_range), interval=200)

    if save:
        writer = PillowWriter(fps=30)
        anim.save("HeiluriSmooth.gif", writer=writer)

    plt.show()


# Creates still images depending on whether one or more oscillators are simulated
def visualisation(oscillators: dict, wigners: list, ax_range: np.ndarray):
    # Plotting if multiple oscillators, also animating wigner function if only one oscillator

    # If more than one oscillator simulated, plots the expectation values for Q and P with respect to time
    # for every oscillator
    if N != 1:
        for key, value in oscillators.items():
            plot_expectation(value["Q"], value["P"], TIMES, f"Expectation values for oscillator {key}")

    # If only one oscillator is simulated, draws a contour plot of the initial state and
    # also shows an animation of the time evolution of said state
    else:
        wigner_non = np.array(wigners)
        wigner_visualization(wigner_non[0], ax_range)

        fig = plt.figure()
        ax = plt.axes(xlim=(MIN_X_AND_Y, MAX_X_AND_Y),
                      ylim=(MIN_X_AND_Y, MAX_X_AND_Y), xlabel='Q', ylabel='P', aspect='equal')

        wigner_animation(wigner_non, ax_range, fig, SAVE)


# Plots the expectation values with respect to time
def plot_expectation(Q_values: list, P_values: list, times: np.ndarray, label: str):
    fig, (ax1, ax2, ax3) = plt.subplots(3)
    ax1.plot(times, [i[0] for i in Q_values], label="Q")
    ax1.plot(times, [i[0] for i in P_values], label="P")
    ax1.set_title("Noninteracting S")
    ax1.legend()

    ax2.plot(times, [i[1] for i in Q_values], label="Q")
    ax2.plot(times, [i[1] for i in P_values], label="P")
    ax2.set_title("Interacting S")
    ax2.legend()

    ax3.plot(times, [i[2] for i in Q_values], label="Q")
    ax3.plot(times, [i[2] for i in P_values], label="P")
    ax3.set_title("Old S")
    ax3.legend()

    fig.tight_layout()

    plt.show()


def main():
    # Starting the runtime -timer
    start = timeit.default_timer()

    # The network
    G, A, eigenvalues, K = network(True)

    # Range for where Wigner function is calculated
    ax_range = np.linspace(MIN_X_AND_Y, MAX_X_AND_Y, RESOLUTION)

    # Creates a grid for the evaluation of the wigner function
    grid = []
    for i in ax_range:
        row = []
        for j in ax_range:
            row.append((j, i))
        grid.append(np.array(row))
    grid = np.array(grid)

    # A dictionary into which every oscillators' expectation values will be saved to
    oscillators = {}

    # Storage for the values of the Wigner function at each instance in time
    wigner_values = []

    # Vectorizes the function that calculates the expectation values for Q^2 and applies it to get the
    # expectation values in an array form
    E_Q2_vector = np.vectorize(expectation_value_Q2)
    Q2_expectation = E_Q2_vector(frequencies)

    # Does the same vectorization and calculations for P^2 as before for Q^2
    E_P2_vector = np.vectorize(expectation_value_P2)
    P2_expectation = E_P2_vector(frequencies)

    # Initial covariance matrix of the network
    cov_X_initial = initial_cov_matrix(zero_block, frequencies, Q2_expectation, P2_expectation)

    # Iterates the initial state in three different bases
    for t in TIMES:
        # The corresponding symplectic matrix S in the non-interacting base for the value of t
        S_non = symplectic(t, K, "non_interacting")
        diagonal_non, new_cov_X_non = new_cov_calculation(S_non, cov_X_initial)

        # If only one oscillator is simulated, th corresponding wigner function is calculated
        if N == 1:
            state_vector = S_non @ initial_state_vector
            wigner_operations(grid, new_cov_X_non, wigner_values, state_vector)

        # S in the interacting base
        S_int = symplectic(t, K, "interacting")
        diagonal_int, new_cov_X_int = new_cov_calculation(S_int, cov_X_initial)

        # S in the old base
        X = np.block([[K.transpose(), zero_block],
                      [zero_block, K.transpose()]])
        S_old = X.transpose() @ S_non @ X
        diagonal_old, new_cov_X_old = new_cov_calculation(S_old, cov_X_initial)

        # Saves the three current covariance matrices
        covariance_save(t, oscillators, diagonal_non, diagonal_int, diagonal_old)

        # A check is done that all the S matrices are still symplectic
        if not sanity_check_1(S_non, S_int, S_old):
            print("The matrix S is not symplectic anymore.")
            break

    stop = timeit.default_timer()
    print(f"\nRuntime: {(stop - start):.4f} s.")

    visualisation(oscillators, wigner_values, ax_range)


if __name__ == '__main__':
    main()
