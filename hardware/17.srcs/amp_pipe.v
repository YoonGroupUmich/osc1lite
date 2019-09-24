`timescale 1ns / 1ps
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////


module amp_pipe(	
	input  wire			ti_clk,					// input clock
	input  wire			reset,					// Opal Kelly reset
	input  wire			clk,					// SPI pipe clock
	input  wire [15:0]	period,					// waveform period
	input  wire [15:0]	num_of_pulses,			// number of pulse
	input  wire         pipe_in_write_trigger,	// write trigger
	input  wire [15:0]  pipe_in_write_data,		// write data
	input  wire			pipe_out_read_trigger,	// read trigger
	output wire [15:0]	pipe_out_read_data, 	// read data
	output wire 		khan	
	    );

reg  read_toggle;
wire pipe_out_read;
reg  write_toggle;
wire pipe_in_write;

reg [15:0]	read_counter;		
reg [15:0]	next_read_counter;
reg [15:0]	write_counter;
reg [15:0]	next_write_counter;
reg [15:0]	complete_pulse_counter;
reg [15:0]	next_complete_pulse_counter;

reg 		state_write;	// 00: ~read & ~write   01: write  10: ~write & read
reg 		next_state_write;
reg 		state_read;
reg			next_state_read;

wire [15:0] data_out;

assign khan = reset ? 0 
			: (pipe_in_write == 1'b1) ? 0 
			: (num_of_pulses == 16'b0) ? 0 
			: ((pipe_out_read | state_read == 1'b1) && (complete_pulse_counter < num_of_pulses|| (complete_pulse_counter == num_of_pulses && read_counter == 0))) ? (read_counter >= 0 && read_counter <= 16'd400) 
			: 0;

assign pipe_out_read = pipe_out_read_trigger | read_toggle;
assign pipe_in_write = pipe_in_write_trigger | write_toggle;

assign pipe_out_read_data = reset ? 0 
						: (pipe_in_write == 1'b1) ? 0 
						: (num_of_pulses == 16'b0) ? 0 
						: ((pipe_out_read | state_read == 1'b1) && (complete_pulse_counter < num_of_pulses|| (complete_pulse_counter == num_of_pulses && read_counter == 0))) ? data_out 
						: 0;
			 
blk_mem_gen_0 memory( 
	.clka(ti_clk),				// input clka  
	.wea(pipe_in_write),		// input [0 : 0] wea 
	.addra(write_counter), 		// input [15 : 0] addra 
	.dina(pipe_in_write_data), 	// input [15 : 0] dina 
	.doutb(data_out), 			// output [15 : 0] douta);
	.addrb(read_counter),
	.clkb(clk)
);	

always @ (posedge clk) begin
	if(reset) begin
	read_counter 			<= 16'b0;
	state_read        		<= 1'b0;	
	complete_pulse_counter 	<= 16'b0;
	end
	else begin
	read_counter 		 	<= next_read_counter;	
	state_read         		<= next_state_read;	
	complete_pulse_counter 	<= next_complete_pulse_counter;
	end
end

always @ (posedge ti_clk) begin
	if(reset) begin
		write_counter 	<= 16'b0;
		state_write		<= 1'b0;
		read_toggle     <= 1'b0;
		write_toggle    <= 1'b0;
	end
	
	else begin
		write_counter	<= next_write_counter;
		state_write		<= next_state_write;
	
		if(pipe_out_read_trigger)		read_toggle <= 1'b1;
		else if(pipe_in_write_trigger)	read_toggle <= 1'b0;
		
		if(pipe_out_read_trigger)		write_toggle <= 1'b0;
		else if(pipe_in_write_trigger)	write_toggle <= 1'b1;
	end
end

always @ (*) begin	
	case(state_write)
		1'b0: 	begin
					if(pipe_in_write_trigger)		next_write_counter = write_counter + 1;
					else if(pipe_out_read_trigger) 	next_write_counter = 0;
					else 							next_write_counter = write_counter;
					
					if(pipe_in_write_trigger)		next_state_write = 1'b1;
					else							next_state_write = 1'b0;
				end
		1'b1: 	begin // write
					next_write_counter = write_counter + 1;	// Need reset to re-write mem.				
					if(pipe_in_write_trigger)		next_state_write = 1'b1;
					else							next_state_write = 1'b0;	
				end
		default:begin
					if(pipe_in_write_trigger)		next_write_counter = write_counter + 1;
					else 							next_write_counter = write_counter;
					
					if(pipe_in_write_trigger)		next_state_write = 1'b1;
					else							next_state_write = 1'b0;				
				end
	endcase		
	
	
	case(state_read)
		1'b0: 	begin
					if(pipe_out_read)	next_read_counter = read_counter + 1;
					else				next_read_counter = 0;					
					if(pipe_out_read)	next_state_read = 1'b1;
					else				next_state_read = 1'b0;					
					next_complete_pulse_counter = 0;
				end
				
		1'b1: 	begin // read
					next_complete_pulse_counter = complete_pulse_counter;					
					if(pipe_in_write) begin // read -> write			
						next_read_counter = 0;
					end else if(pipe_out_read && read_counter + 1 == period[15:0]) begin // finish one period		   
						next_read_counter = 0;
						next_complete_pulse_counter = complete_pulse_counter + 1;
					end else if(pipe_out_read && read_counter == 16'b1111111111111111) begin
						next_read_counter = read_counter;
					end else if(pipe_out_read) begin	   
						next_read_counter = read_counter + 1;
					end else begin 							
						next_read_counter = 0;
					end
											
					if(pipe_in_write)	next_state_read = 1'b0;
					else				next_state_read = 1'b1;	
					
					if(complete_pulse_counter == 16'b1111111111111110)
						next_complete_pulse_counter = complete_pulse_counter;					
				end
		default: begin
					if(pipe_out_read)	next_read_counter = read_counter + 1;
					else				next_read_counter = 0;
					
					if(pipe_out_read)	next_state_read = 1'b1;
					else				next_state_read = 1'b0;
					
					next_complete_pulse_counter = 0;
			   end
	endcase		
end

endmodule