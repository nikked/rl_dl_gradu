import unittest

import train_test_analyse_rl_algorithm


class TestTrainTestAnalyse(unittest.TestCase):
    def setUp(self):
        self.cli_options = {
            "crypto_data": False,
            "gpu_device": None,
            "interactive_session": False,
            "max_no_of_training_periods": 100,
            "no_of_assets": 2,
            "plot_analysis": False,
            "verbose": False,
        }

    def test_train_completes_fully(self):

        train_test_analyse_rl_algorithm.main(**self.cli_options)

        self.assertEqual(True, True)


if __name__ == "__main__":
    unittest.main()
