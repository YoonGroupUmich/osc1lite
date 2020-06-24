#include <math.h>
#include <stdio.h>

const double pi = acos(-1);

const double duration = 10;  // ms
const double amplitude_max = 100;  // uA
const char output_file[] = "sine.cwave";

int main() {
    int clock_div = (int)(ceil(duration * 1000 / 17.152 / 0x7fff));
    int num_of_samples = (int)(round(duration * 1000 / 17.152 / clock_div));

    FILE* fp = fopen(output_file, "w");
    for (int i = 0; i < num_of_samples; ++i)
        fprintf(fp, "%f\n", (1 - cos(i * pi / num_of_samples * 2)) * amplitude_max / 2);
    fclose(fp);

    printf("Generated %d samples. Please use %.3f us as sample interval.\n",
        num_of_samples, clock_div * 17.152);

    return 0;
}
