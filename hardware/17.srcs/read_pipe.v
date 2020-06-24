`timescale 1ns / 1ps
/////////////////////////////////////////////////
// OSC1 - LITE
// Version 1.0.0
// Yoon's Lab - U of M
/////////////////////////////////////////////////

// Read data from okPipeIn
// Parse the wire protocol
// And store custom waveform to BRAM

module read_pipe(
    input wire rst,
    input wire clk,
    
    input wire pipe_data_ready,
    input wire [15:0] pipe_data,
    
    output wire [15:0] mem_addr,
    output wire [1:0] mem_write,
    output wire [17:0] mem_data,
    
    output reg [14:0] cw_clk_div,
    output reg [44:0] cw_waveform_len
);
    reg state;  // 0: idle / metadata, 1: waveform
    reg [1:0] waveform_index_minus_one;
    reg [14:0] read_counter;
    
    assign mem_addr = {waveform_index_minus_one, read_counter[14:1]};
    assign mem_write[1] = state & read_counter[0];
    assign mem_write[0] = state & ~read_counter[0];
    assign mem_data = {pipe_data[8:0], pipe_data[8:0]};
    
    always @(posedge clk) begin
        if (rst) begin
            cw_clk_div <= 0;
            cw_waveform_len <= 0;
            state <= 0;
            read_counter <= 0;
        end else if (pipe_data_ready) begin
            if (state == 0) begin
                if (read_counter == 0) begin
                    if (pipe_data == 16'h7363) begin
                        read_counter <= 1;
                    end
                end else if (read_counter == 1) begin
                    if (pipe_data == 16'h0a77) begin
                        read_counter <= 2;
                    end else begin
                        read_counter <= 0;
                    end
                end else if (read_counter == 2) begin
                    waveform_index_minus_one <= pipe_data[1:0] - 1;
                    cw_clk_div[(pipe_data[1:0] - 1) * 5 +: 5] <= pipe_data[12:8];
                    read_counter <= 3;
                end else if (read_counter == 3) begin
                    state <= 1;
                    read_counter <= 0;
                    cw_waveform_len[waveform_index_minus_one * 15 +: 15] <= pipe_data[14:0];
                end
            end else begin  // state == 1
                if (read_counter + 1 == cw_waveform_len[waveform_index_minus_one * 15 +: 15]) begin
                    state <= 0;
                    read_counter <= 0;
                end else begin
                    read_counter <= read_counter + 1;
                end
            end
        end
    end
endmodule