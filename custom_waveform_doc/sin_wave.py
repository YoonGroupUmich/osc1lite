#!/usr/bin/env python

import math


def main():
    duration = 10  # ms
    amplitude_max = 100  # uA
    output_file = 'sine.cwave'

    clock_div = int(math.ceil(duration * 1000 / 17.152 / 0x7fff))
    num_of_samples = int(round(duration * 1000 / 17.152 / clock_div))

    with open(output_file, 'w') as fp:
        for i in range(num_of_samples):
            print((1 - math.cos(i / num_of_samples * 2 * math.pi)) * amplitude_max / 2, file=fp)

    print('Generated %d samples. Please use %.3f us as sample interval.'
          % (num_of_samples, clock_div * 17.152))


if __name__ == '__main__':
    main()
