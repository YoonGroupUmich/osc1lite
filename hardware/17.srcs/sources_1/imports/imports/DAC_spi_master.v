`timescale 1ns / 1ps
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////


module spi_controller(
	input  wire			clk,				// Opal Kelly ti_clk
	input  wire			rst,				// Opal Kelly reset
	input  wire [2:0]	mode_pc, 			// Opal Kelly write bit: 3'b000 for nop, 3'b001 for write, 3'b010 for read, 3'b011 for control, 3'b100 for reset, 3'b101 for config
	input  wire 		clear_request,		// OK clr DAC pin
	input  wire			pipe,				// 1 if pipe
	input  wire [15:0]	data_from_memory,	// waveform_info from memory
	input  wire [15:0]	data_from_user,		// square waveform_info 
	input  wire 		sdo_bit,			// data read from DAC
	input  wire [1:0]	counter2spi,		// counter from read_input module to modulate the read/write cycle
	input  wire 		no_trig,			// 1 if the channel is paused (wait for trigger) for 20 seconds
	input  wire 		channel_disable,	// 1 if request to disable the channel
	input  wire 		channel_enable,		// 1 if request to enable the channel

	output wire			clear,				// DAC input clr
	output reg			latch,				// DAC input latch
	output wire			sclk,				// DAC input sclk
	output reg			din,				// DAC input din
	output wire			spi_pipe_clk,		// SPI clock for pipe
	output wire [4:0] 	alarm_out,			// alarm signals, refer to dac8750 Page 36 status register
	output reg			config_counter,		// reset the counter
	output wire			channel_is_disable	// 1 if the channel status is disabled
    );

wire [7:0] 	address_byte;
wire [23:0] full_command;
reg	 [23:0] full_command_one_period;
reg  [23:0] full_command_one_period_prev;
reg  [4:0] 	counter;				// 0 - 23 to clock in the command. 24 - 29 to relax latch HIGH. t5 min = 40ns on dac8750 Page 9.
wire [4:0]	shift_counter_helper;	// Shifting bit from full_command to din
wire [2:0] 	mode;
reg			output_en;
reg			output_en_proposed;
wire		next_output_en;
wire		next_output_en_proposed;
reg	 [23:0] alarm;

assign shift_counter_helper = ~counter + 5'd24;  // (0 -> 23, 1 -> 22, etc.)
assign next_output_en = output_en;
assign next_output_en_proposed = output_en_proposed;
assign channel_is_disable = ~output_en;
assign alarm_out = alarm[4:0];
assign clear = clear_request; 	// assign OK clr DAC pin control to clr DAC register. 
assign sclk = ((counter >= 5'd24) | (full_command_one_period == full_command_one_period_prev) )? 0 :clk;

assign mode = ((output_en != output_en_proposed) && (output_en_proposed == 1'b0)) ? 3'b110		// write control, output disable
			: ((output_en != output_en_proposed) && (output_en_proposed == 1'b1)) ? 3'b011		// write control, output enable
			: (counter2spi == 2) ? 3'b111		// DAC read status register
			: (counter2spi == 3) ? 3'b000		// NOP
			: mode_pc;							// DAC write

assign address_byte = (mode == 3'b001) ? 8'b00000001 		// wirte (See dac8750 Page 32, 33)
					: (mode == 3'b010) ? 8'b00000010        // read
					: (mode == 3'b011) ? 8'b01010101        // write control, output enable
					: (mode == 3'b110) ? 8'b01010101        // write control, output disable			
					: (mode == 3'b100) ? 8'b01010110        // write reset
					: (mode == 3'b101) ? 8'b01010111        // write config
					//: (mode == 3'b110) ? 8'b01011000      // write DAC gain calibration, not used here
					//: (mode == 3'b111) ? 8'b01011001      // write DAC zero calibration, not used here
					: (mode == 3'b111) ? 8'b00000010		// read status register
					: 8'b0;			
															
assign full_command = (mode == 3'b010) ?  {address_byte, 16'b0000000000000010} // if read, set read DAC config register
					: (mode == 3'b100) ?  {address_byte, 16'b0000000000000001} // if reset, set RST bit to 1
					: (mode == 3'b011) ?  {address_byte, 16'b0001000000000110} // if set control, output enable, full_command = 24'h551007
					: (mode == 3'b110) ?  {address_byte, 16'b0000000000000110} // if set control, output disable, full_command = 24'h550007
					: (mode == 3'b101) ?  {address_byte, 16'b0000000000000000} // if config, set WD bits to 0
					: (mode == 3'b000) ?  {address_byte, 16'b0000000000000000} // NOP
					: (mode == 3'b111) ?  {address_byte, 16'b0000000000000000} // read status register
					:  pipe ? {address_byte, data_from_memory} 
					: {address_byte, data_from_user};			// if write, {address_byte -> [23:16], data_from_user -> [15:0]}

assign spi_pipe_clk = (counter == 5'd29);

always @ (posedge clk) begin
	if (full_command_one_period_prev == 24'h020000) begin
		if (counter < 5'd24) begin
			alarm[5'd23-counter] = sdo_bit;
		end
	end
end

always @ (negedge clk) begin
	if (rst) begin
		output_en_proposed <= 1'b0;
	end else if (channel_disable) begin
		output_en_proposed <= 1'b0;
	end else if (channel_enable) begin
		output_en_proposed <= 1'b1;
	end else if (output_en && no_trig) begin
		output_en_proposed <= 1'b0;
	end else begin
		output_en_proposed <= next_output_en_proposed;
	end
end

always @ (negedge clk) begin
	if(rst | channel_disable) begin
		counter <= 0;
	end else begin
		counter <= counter + 1;
	end
end

always @ (negedge clk) begin
	if (full_command_one_period == full_command_one_period_prev) begin
		latch <= 1'b0;
	end else begin 
		if(counter >= 5'd23) begin
			if(counter < 5'd29) begin
				latch <= 1'b1;
			end else begin
				latch <= 1'b0;
			end
		end else begin
			latch <= 1'b0;
		end
	end
end

always @ (*) begin
	if(counter >= 5'd23) begin
		if(counter < 5'd24) begin
			din = (full_command_one_period >> shift_counter_helper) & 1'b1;
		end else if(counter < 5'd29) begin
			din = 1'b0;
		end else begin
			din = 1'b0;
		end
	end else begin
		din = (full_command_one_period >> shift_counter_helper) & 1'b1;
	end
end

always @ (negedge clk) begin
	if (counter == 5'd31) begin
		full_command_one_period <= full_command;
		full_command_one_period_prev <= full_command_one_period;
	end

	if (rst) begin
		output_en <= 1'b0;
	end else if (full_command_one_period == 24'h551006) begin // enable output
		output_en <= 1'b1;
	end else if (full_command_one_period == 24'h550006) begin // disable output
		output_en <= 1'b0;
	end else begin
		output_en <= next_output_en;
	end
	
	if (counter == 5'd31 && full_command_one_period == 24'h551006) begin
		config_counter <= 1'b1;
	end else begin
		config_counter <= 1'b0;
	end
end
		
endmodule
