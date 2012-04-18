message CheckSignature {
    required string hostname = 1;
    required string signed_data = 2;
    required bytes signature = 3;
    optional string algorithm = 4;
}

message CheckSignatureWithCert {
    required string cert = 1;
    required string signed_data = 2;
    required bytes signature = 3;
    optional string algorithm = 4;
}

message DerivateKey {
    required string ikm = 1;
    required string salt = 2;
    required string info = 3;
    required int32 l = 4;
    required string hashmod = 5;
}

message StringResponse {
    optional string error_type = 1;
    optional string error = 2;
    optional string value = 3;
}

message Response {
    optional string error_type = 1;
    optional string error = 2;
    optional bool value = 3;
}
