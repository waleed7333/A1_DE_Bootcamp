# MongoDB Assignment - School Database

## 📚 Project Overview
This project contains solutions for a comprehensive MongoDB assignment consisting of 9 tasks covering essential database operations including CRUD operations, queries, updates, aggregation pipelines, and array manipulations.

## 🗄️ Database Structure
- **Database Name**: `school`
- **Collection Name**: `students`
- **Environment**: MongoDB Local Instance

## 📋 Tasks Completed

### Task 1: Create and Insert Data
- Created database `school` and collection `students`
- Inserted a single student document using `insertOne()` method

### Task 2: Insert Multiple Documents
- Inserted multiple student records in a single operation using `insertMany()` method

### Task 3: Querying Documents
- Queried students majoring in Mathematics using field-based filtering
- Queried students older than 20 using the `$gt` comparison operator

### Task 4: Update a Document
- Updated Noah's major to "Computer Science" using the `$set` update operator with `updateOne()`

### Task 5: Remove a Field
- Removed the `age` field from Emma's document using the `$unset` operator

### Task 6: Use Operators for Advanced Queries
- Queried students with ages between 20 and 22 inclusive using `$gte` and `$lte` operators

### Task 7: Use Aggregation Pipeline
- Counted the number of students per major using the `$group` aggregation stage

### Task 8: Field Comparison with $expr
- Inserted students with `marks` and `passingMarks` fields
- Found students whose marks are less than passingMarks using the `$expr` operator

### Task 9: Use Array Queries
- Inserted a student with an array of courses
- Added a new course using the `$push` update operator
- Retrieved students enrolled in a specific course using array querying

## 🛠️ Technologies Used
- **MongoDB** (Local Server Installation)
- **MongoDB Shell** (`mongosh`) - Command-line interface
- **MongoDB Compass** - Official GUI for database management

## 📁 Files Included
- `solution.mongodb` - Contains all MongoDB commands for all 9 tasks
- `school.students.json` - Exported JSON data from the students collection
- `README.md` - Project documentation (this file)

## 🚀 How to Run (Official MongoDB Methods)

### Prerequisites
- MongoDB installed locally on your system
- MongoDB Server running as a Windows service
- MongoDB Compass (optional, for GUI management)
- MongoDB Shell (`mongosh`) for command-line execution

### Method 1: Using MongoDB Shell (mongosh)

1. **Start MongoDB Server**
   ```bash
   net start MongoDB
   ```

2. **Open MongoDB Shell**
   ```bash
   mongosh
   ```

3. **Select Database**
   ```javascript
   use school
   ```

4. **Execute Commands**
   - Copy commands from `solution.mongodb`
   - Paste into the shell one by one
   - Press Enter after each command

5. **Verify Results**
   ```javascript
   db.students.find().pretty()
   ```

### Method 2: Using MongoDB Compass (Official GUI)

1. **Launch MongoDB Compass**
   - Open the application from your Start Menu

2. **Connect to Local Instance**
   - Connection String: `mongodb://localhost:27017/`
   - Click "Connect"

3. **Create Database**
   - Click "Create Database"
   - Database Name: `school`
   - Collection Name: `students`
   - Click "Create Database"

4. **Execute Commands**
   - Navigate to the `students` collection
   - Click the "MongoDB Shell" or "Query" tab
   - Paste and execute commands from `solution.mongodb`

5. **View Data**
   - Data appears immediately in the collection view
   - Use filters and aggregations for advanced queries

### Method 3: Using MongoDB Shell Script

1. **Create a Script File**
   - Save the contents of `solution.mongodb` as `script.js`

2. **Execute the Script**
   ```bash
   mongosh --file script.js
   ```

3. **View Results**
   - Output appears directly in the terminal

## 📊 Sample Output

### Exported Data from Collection
Below is the JSON data exported from the `students` collection after completing all tasks:

```json
[
  {
    "_id": { "$oid": "6a33b0db4f7b283f41738e12" },
    "name": "Ahmed",
    "age": 20,
    "major": "Math",
    "grade": 85
  },
  {
    "_id": { "$oid": "6a33b119323c230d06897ce0" },
    "name": "Ahmed",
    "age": 20,
    "major": "Math",
    "grade": 85
  },
  {
    "_id": { "$oid": "6a33b119323c230d06897ce1" },
    "name": "Sara",
    "age": 22,
    "major": "Physics",
    "grade": 90
  },
  {
    "_id": { "$oid": "6a33b119323c230d06897ce2" },
    "name": "Mohamed",
    "age": 19,
    "major": "Computer Science",
    "grade": 88
  },
  {
    "_id": { "$oid": "6a33b119323c230d06897ce3" },
    "name": "Ali",
    "major": "Math",
    "marks": 60,
    "passingMarks": 70
  },
  {
    "_id": { "$oid": "6a33b119323c230d06897ce4" },
    "name": "Layla",
    "major": "Physics",
    "marks": 80,
    "passingMarks": 75
  },
  {
    "_id": { "$oid": "6a33b119323c230d06897ce5" },
    "name": "Omar",
    "age": 21,
    "major": "Engineering",
    "courses": [
      "Math 101",
      "Physics 101",
      "Chemistry 101",
      "Computer Science 101",
      "Computer Science 101"
    ]
  }
]
```

### Sample Query Outputs

**Find Math Students:**
```json
[
  { "name": "Ahmed", "age": 20, "major": "Math" },
  { "name": "Ali", "major": "Math", "marks": 60, "passingMarks": 70 }
]
```

**Aggregation - Students per Major:**
```json
[
  { "_id": "Math", "count": 2 },
  { "_id": "Physics", "count": 1 },
  { "_id": "Computer Science", "count": 1 },
  { "_id": "Engineering", "count": 1 }
]
```

## 📝 Key Query Examples

### Find students between age 20 and 22
```javascript
db.students.find({
    age: { $gte: 20, $lte: 22 }
})
```

### Update a student's major
```javascript
db.students.updateOne(
    { name: "Noah" },
    { $set: { major: "Computer Science" } }
)
```

### Find students with low marks (below passing)
```javascript
db.students.find({
    $expr: {
        $lt: ["$marks", "$passingMarks"]
    }
})
```

### Add a new course to a student
```javascript
db.students.updateOne(
    { name: "Omar" },
    { $push: { courses: "Computer Science 101" } }
)
```

### Find students enrolled in a specific course
```javascript
db.students.find({
    courses: "Math 101"
})
```

## 🔍 Verification Commands

To view all data:
```javascript
db.students.find().pretty()
```

To count total documents:
```javascript
db.students.count()
```

To view collection indexes:
```javascript
db.students.getIndexes()
```

## 📌 Important Notes

- All commands use the `use('school')` statement to select the database
- The `_id` field is automatically generated by MongoDB
- Duplicate entries may appear if commands were executed multiple times
- Arrays demonstrate MongoDB's flexibility with nested data structures
- The `$expr` operator allows field-to-field comparisons

## 🔧 Troubleshooting

### MongoDB Service Not Running
```bash
net start MongoDB
```

### Cannot Connect to Local Instance
- Ensure MongoDB is installed correctly
- Check if service is running
- Verify port 27017 is not blocked

### Duplicate Documents
- Remove duplicates using:
```javascript
db.students.aggregate([
  { $group: { _id: "$name", uniqueIds: { $addToSet: "$_id" }, count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
])
```

## 📚 Learning Outcomes

After completing this assignment, you should be able to:
- Perform basic CRUD operations in MongoDB
- Write complex queries using comparison operators
- Update documents using `$set` and `$unset` operators
- Use aggregation pipelines for data analysis
- Work with arrays and nested documents
- Compare fields within documents using `$expr`

## 🤝 Contribution

This is a completed assignment for educational purposes.

## 📧 Contact

For questions regarding this assignment, contact your course instructor.

---

**📅 Date**:  17 June 2026

**👨‍💻 Student**: Waleed Alabbasi

**📚 Course**: MongoDB Database Operations
