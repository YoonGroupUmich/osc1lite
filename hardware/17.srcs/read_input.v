`timescale 1ns / 1ps
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////


module read_input( 								// need to be called 12 times 
    input wire			clk,					// input clock
    input wire			rst,					// Opal Kelly reset
	input wire			new_trig_in,			// 1 if detect overlapped trigger in 		
    input wire [15:0] 	amplitude,				// amplitude of square waves 
    input wire [19:0] 	Cmax,					// waveform period, Cmax = clk frequency/sampling frequency - 1
    input wire [19:0] 	Cth,					// waveform pulse width, Dutycycle * (Cmax + 1)
    input wire [3:0] 	Option,					// choose rising time: 0 for 0 msec, 1 for 0.1 msec, 2 for 0.5 msec, 3 for 1 msec, 4 for 2 msec
    input wire [15:0] 	wave_number_of_pulse,	// number of pulses
	input wire 			flag,					// 1 to output waveform
	input wire 			trig_out_valid,			// 1 if the user wants the trigger out signal
	input wire 			config_counter,			// reset the counter
	input wire 			channel_disable,		// Request to disable the channel
	input wire 			trig_mode,				// 0 is one-shot, 1 is continuous
    
	output wire [15:0] 	result,					// square wave info of one module
    output wire 		resetflag,				// 1 if request for no output waveform
	output wire 		trig_out,				// trig out info
	output wire [1:0] 	counter2spi				// counter to SPI module to modulate the read/write cycle
   );
   
    reg [31:0] counter = 0;		// clock counter
    reg [15:0] counter1 = 0;	// number of waves have been output
    wire [6:0] mult;			// waveform rising/falling edge width
	wire [21:0] rising_edge;	// waveform info at rising edge
	wire [21:0] falling_edge;	// waveform info at falling edge
	wire [13:0] fixed;			
	
	assign counter2spi = counter[6:5];    
	assign rising_edge = amplitude*counter[26:7]*fixed;
	assign falling_edge = amplitude*(Cth + 1 - counter[26:7])*fixed;
    assign resetflag = ((trig_mode == 1'b0) && (counter1 == wave_number_of_pulse)) ? 1'b1 : 1'b0;
    assign mult = (Option == 4'd0) ? 7'd1
                : (Option == 4'd1) ? 7'd6
                : (Option == 4'd2) ? 7'd29
                : (Option == 4'd3) ? 7'd58
                : (Option == 4'd4) ? 7'd116
                :  6'd0;
				
	assign fixed = (Option == 4'd0) ? 14'h2000
                : (Option == 4'b1) ? 14'h0555
                : (Option == 4'd2) ? 14'h011a
                : (Option == 4'd3) ? 14'h008d
                : (Option == 4'd4) ? 14'h0047
                :  6'd0;
   
    assign result = (flag == 0) ? 1'b0
					:(counter[26:7] < mult) ? ({7'b0, rising_edge[21:13]})
					:(counter[26:7] <= (Cth - mult)) ? ({7'b0, amplitude[8:0]})
					:(counter[26:7] <= Cth) ? ({7'b0, falling_edge[21:13]})
					: 1'b0;
					
	assign trig_out = (result != 16'b0 && trig_out_valid == 1'b1) ? 1'b1 : 1'b0;

	always @ (negedge clk) begin
		if (rst | channel_disable) counter <= 0;
		else if (flag == 0 | new_trig_in == 1'b1 | config_counter) counter <= 0;
		else if (counter[26:7] >= Cmax) counter <= 1;
		else counter <= counter + 1;
	end
	
	always @ (negedge clk) begin
		if (rst | channel_disable) counter1 <= 0;
		else if (flag == 0 | new_trig_in == 1'b1 | config_counter) counter1 <= 0;
		else if ((trig_mode == 1'b1) && (counter1 == wave_number_of_pulse)) counter1 <= wave_number_of_pulse;
		else if (counter[26:7] >= Cmax) counter1 <= counter1 + 1;
	end

endmodule